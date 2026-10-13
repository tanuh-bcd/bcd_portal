import math
import json
import uuid
import datetime
import hashlib
import threading
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db.session import get_questionnaire_db, get_db
from ..core.config import settings
from .auth import get_current_user
from ..models.models import ModelWeightsVersionControl, ModelWeights, RiskThresholdsVersionControl, RiskThresholds, Question, QuestionnaireVersion, Hospital
from google.cloud import storage
from pydantic import BaseModel
from typing import Any, Dict, Optional

router = APIRouter()


@router.get("/participant-information")
def get_participant_information(
    lang: str = "en",
    version: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Return database-managed Participant Information with English fallback."""
    row = db.execute(
        text(
            "SELECT content_json FROM participant_information_translations "
            "WHERE version_number = COALESCE(:version, (SELECT version_number FROM questionnaire_versions "
            "  WHERE is_active = 1 ORDER BY version_number DESC LIMIT 1)) "
            "AND language_code IN (:lang, 'en') AND is_active = 1 "
            "ORDER BY CASE WHEN language_code = :lang THEN 0 ELSE 1 END LIMIT 1"
        ),
        {"lang": lang, "version": version},
    ).scalar()
    if row is None:
        raise HTTPException(status_code=404, detail="Participant information not configured")
    return json.loads(row) if isinstance(row, str) else row

_questionnaire_json_path = Path(__file__).resolve().parent / "questionnaire_en.json"
_QUESTION_TEXT_MAP: Dict[str, str] = {}
if _questionnaire_json_path.exists():
    with open(_questionnaire_json_path, encoding="utf-8") as _f:
        _QUESTION_TEXT_MAP = {k: v.get("question", k) for k, v in json.load(_f).get("questions", {}).items()}


def _get_active_weights(app_db: Session) -> Dict[str, float]:
    active_version = (
        app_db.query(ModelWeightsVersionControl)
        .filter(ModelWeightsVersionControl.is_active == True)
        .first()
    )
    if not active_version:
        raise HTTPException(status_code=500, detail="No active model weights version found")

    rows = (
        app_db.query(ModelWeights)
        .filter(ModelWeights.version_number == active_version.version_number)
        .all()
    )
    return {row.feature_name: float(row.weight_value) for row in rows}


def _get_active_thresholds(app_db: Session):
    active_version = (
        app_db.query(RiskThresholdsVersionControl)
        .filter(RiskThresholdsVersionControl.is_active == True)
        .first()
    )
    if not active_version:
        raise HTTPException(status_code=500, detail="No active risk thresholds version found")

    return (
        app_db.query(RiskThresholds)
        .filter(RiskThresholds.version_number == active_version.version_number)
        .all()
    )

def calculate_snehitha_risk(
    form_data: dict,
    weights: Dict[str, float],
    questionnaire_version: int = 1,
) -> str:
    if questionnaire_version == 2:
        age = int(form_data.get("V2_Q03", 0) or 0)
        age_at_menarche = int(form_data.get("V2_Q11A", 0) or 0)
        irregular_cycles = 1 if form_data.get("V2_Q11_CYCLES") == "No" else 0
        breastfeeding_24m = 1 if form_data.get("V2_Q13E") == "Greater than 24 months" else 0
        first_degree_relatives = 1 if form_data.get("V2_Q17A") == "First Order (Mother, Sibling, Father)" else 0
        # Version 2 intentionally has no previous-biopsy question.
        previous_biopsy = 0
        is_nullipara = form_data.get("V2_Q13") == "No"
        age_first_birth = form_data.get("V2_Q13_AGE_FIRST_BIRTH")
    else:
        age = int(form_data.get("Q1", 0) or 0)
        age_at_menarche = int(form_data.get("Q10", 0) or 0)
        irregular_cycles = 1 if form_data.get("Q12_Current") == "No" else 0
        breastfeeding_24m = 1 if form_data.get("Q17") == "greater than 24 months" else 0
        first_degree_relatives = 1 if form_data.get("Q21") == "First Order (Mother, Sibling, Father)" else 0
        previous_biopsy = 1 if form_data.get("Q40") == "Yes" else 0
        is_nullipara = form_data.get("Q14") == "No"
        age_first_birth = form_data.get("Q16")

    age_first_birth_25_29 = age_first_birth == "25 to 29"
    age_first_birth_gte30 = age_first_birth == "After 30"

    age_first_live_birth_2529_or_nullipara = 1 if (is_nullipara or age_first_birth_25_29) else 0
    age_first_live_birth_30_or_more = 1 if age_first_birth_gte30 else 0

    logit_p = (
        weights["intercept"]
        + weights["age"] * age
        + weights["age_at_menarche"] * age_at_menarche
        + weights["irregular_cycles"] * irregular_cycles
        + weights["breastfeeding_24m"] * breastfeeding_24m
        + weights["first_degree_relatives"] * first_degree_relatives
        + weights["previous_biopsy"] * previous_biopsy
        + weights["age_first_live_birth_2529_or_nullipara"] * age_first_live_birth_2529_or_nullipara
        + weights["age_first_live_birth_30_or_more"] * age_first_live_birth_30_or_more
    )

    probability = 1 / (1 + math.exp(-logit_p))
    risk_percentage = round(probability * 100, 2)
    if math.isnan(risk_percentage):
        risk_percentage = 0.00
    return str(risk_percentage)


def determine_risk_category(risk_decimal: float, thresholds) -> str:
    for t in thresholds:
        lo = float(t.min_percentage) if t.min_percentage is not None else float("-inf")
        hi = float(t.max_percentage) if t.max_percentage is not None else float("inf")
        if lo <= risk_decimal < hi:
            return t.risk_category
    return "Unknown"


@router.post("/session/start")
def start_session(
    request: Request,
    version: Optional[int] = None,
    db: Session = Depends(get_questionnaire_db),
    app_db: Session = Depends(get_db),
):
    session_id = str(uuid.uuid4())
    ip_address = request.client.host if request.client else "unknown"
    now = datetime.datetime.utcnow()

    try:
        version_query = app_db.query(QuestionnaireVersion)
        if version is None:
            selected_version = version_query.filter(
                QuestionnaireVersion.is_active == True
            ).order_by(QuestionnaireVersion.version_number.desc()).first()
            if not selected_version:
                raise HTTPException(status_code=500, detail="No active questionnaire version configured")
        else:
            selected_version = version_query.filter(
                QuestionnaireVersion.version_number == version
            ).first()
            if not selected_version:
                raise HTTPException(status_code=404, detail="Questionnaire version not found")
        db.execute(text(
            "INSERT INTO session_table "
            "(session_id, ip_address, session_start_time, questionnaire_version) "
            "VALUES (:sid, :ip, :ts, :version)"
        ), {"sid": session_id, "ip": ip_address, "ts": now, "version": selected_version.version_number})
        db.commit()
        return {
            "success": True,
            "sessionId": session_id,
            "questionnaireVersion": selected_version.version_number,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail="Could not start session. Please try again.")


@router.post("/session/{session_id}/consent")
async def upload_public_consent(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_questionnaire_db)
):
    session = db.execute(
        text("SELECT session_id FROM session_table WHERE session_id = :sid"),
        {"sid": session_id}
    ).fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    content = await file.read()
    extension = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'jpg'
    upload_date = datetime.datetime.utcnow().strftime("%Y%m%d")
    blob_name = f"tanuh-data-capture/consent/{session_id}_consent_{upload_date}.{extension}"

    client = storage.Client()

    bucket = client.bucket(settings.GCP_STORAGE_BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(content, content_type=file.content_type or "application/octet-stream")
    gcs_url = f"gs://{settings.GCP_STORAGE_BUCKET}/{blob_name}"

    db.execute(
        text("UPDATE session_table SET consent_url = :url WHERE session_id = :sid"),
        {"url": gcs_url, "sid": session_id},
    )
    db.commit()

    return {"success": True, "consent_url": gcs_url}


class SubmitPayload(BaseModel):
    sessionId: str
    formDataEn: Dict[str, Any]


def _subject_and_institute(form_data, version):
    if version == 2:
        return str(form_data.get("V2_Q01") or "").strip(), str(form_data.get("V2_Q02") or "").strip()
    return str(form_data.get("Q44") or "").strip(), str(form_data.get("Q45") or "").strip()


def _subject_exists(db, subject_id, institute, session_id):
    return db.execute(text("""
        SELECT 1 FROM session_data_table subject
        JOIN session_data_table institution ON institution.session_id = subject.session_id
        WHERE subject.session_id <> :sid
          AND (subject.question_key IN ('V2_Q01', 'Q44')
               OR subject.question IN ('Enter your Patient ID(if any, else leave):',
                   'Enter your subject ID:', 'Enter Subject ID (if any, else leave)', 'Q44'))
          AND (institution.question_key IN ('V2_Q02', 'Q45')
               OR institution.question IN ('Institute Name', 'Institute Name:',
                   'Enter the Hospital ID(If any, else leave):',
                   'Enter the Institution Name (if any, else leave)',
                   'Enter the Institution Name (If any, else leave)', 'Q45'))
          AND LOWER(TRIM(subject.answer)) = LOWER(:subject_id)
          AND LOWER(TRIM(institution.answer)) = LOWER(:institute)
        LIMIT 1 FOR UPDATE
    """), {"sid": session_id, "subject_id": subject_id, "institute": institute}).first() is not None


@router.get("/subject-id/availability")
def subject_id_availability(
    subject_id: str,
    db: Session = Depends(get_questionnaire_db),
    app_db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    subject_id = subject_id.strip()
    if not subject_id or len(subject_id) > 255:
        raise HTTPException(status_code=400, detail="Enter a valid Subject ID.")
    hospital_id = current_user.get("hospital_id")
    hospital = app_db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=403, detail="Hospital not found for this user.")
    return {"exists": _subject_exists(db, subject_id, hospital.name, "")}


class PublicSubjectAvailabilityPayload(BaseModel):
    sessionId: str
    subjectId: str
    institution: str


_public_checks = {}
_public_checks_lock = threading.Lock()


@router.post("/subject-id/availability/public")
def public_subject_id_availability(
    payload: PublicSubjectAvailabilityPayload,
    db: Session = Depends(get_questionnaire_db),
    app_db: Session = Depends(get_db),
):
    subject_id = payload.subjectId.strip()
    institution = payload.institution.strip()
    if not subject_id or not institution or len(subject_id) > 255 or len(institution) > 255:
        raise HTTPException(status_code=400, detail="Enter a valid Subject ID and institution.")
    session = db.execute(text(
        "SELECT session_end_time FROM session_table WHERE session_id = :sid "
        "AND session_start_time > :cutoff"
    ), {"sid": payload.sessionId,
        "cutoff": datetime.datetime.utcnow() - datetime.timedelta(hours=24)}).first()
    if not session or session[0] is not None:
        raise HTTPException(status_code=404, detail="Active questionnaire session not found.")
    hospital = app_db.query(Hospital).filter(Hospital.name == institution).first()
    if not hospital:
        raise HTTPException(status_code=400, detail="Select a valid institution.")
    now = time.monotonic()
    with _public_checks_lock:
        # Limit a session to ten distinct IDs; avoid an unrestricted public lookup.
        if len(_public_checks) > 10000:
            _public_checks.clear()
        expires, checked_ids = _public_checks.get(payload.sessionId, (0, set()))
        if expires < now:
            checked_ids = set()
        identity = (hospital.id, subject_id.casefold())
        if identity not in checked_ids and len(checked_ids) >= 10:
            raise HTTPException(status_code=429, detail="Too many Subject ID checks for this questionnaire.")
        checked_ids.add(identity)
        _public_checks[payload.sessionId] = (now + 3600, checked_ids)
    return {"exists": _subject_exists(db, subject_id, hospital.name, payload.sessionId)}


@router.post("/submit")
def submit_questionnaire(
    payload: SubmitPayload,
    db: Session = Depends(get_questionnaire_db),
    app_db: Session = Depends(get_db),
):
    session_id = payload.sessionId
    form_data_en = payload.formDataEn

    if not session_id or not form_data_en:
        raise HTTPException(status_code=400, detail="Session ID and form data are required.")

    session_row = db.execute(
        text("SELECT session_id, questionnaire_version FROM session_table WHERE session_id = :sid"),
        {"sid": session_id},
    ).fetchone()
    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found. Please start a new questionnaire.")

    try:
        questionnaire_version = int(session_row[1] or 1)
        subject_id, institute = _subject_and_institute(form_data_en, questionnaire_version)
        lock_name = None
        lock_connection = None
        if subject_id and not institute:
            raise HTTPException(status_code=400, detail="Please select an institution for this Subject ID.")
        if subject_id and institute:
            lock_name = "subject:" + hashlib.sha256(
                f"{institute.casefold()}\0{subject_id.casefold()}".encode()
            ).hexdigest()[:48]
            lock_connection = db.get_bind().connect()
            if lock_connection.execute(text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}).scalar() != 1:
                raise HTTPException(status_code=503, detail="Could not check Subject ID. Please try again.")
            if _subject_exists(db, subject_id, institute, session_id):
                raise HTTPException(status_code=409, detail="Subject ID already exists for this institution. Please create a new Subject ID.")
        risk_percentage = None
        risk_cat = None
        weights = _get_active_weights(app_db)
        thresholds = _get_active_thresholds(app_db)
        risk_percentage = calculate_snehitha_risk(
            form_data_en, weights, questionnaire_version
        )
        risk_pct_float = float(risk_percentage)
        risk_decimal = round(risk_pct_float / 100, 4)
        risk_cat = determine_risk_category(risk_decimal, thresholds)

        question_rows = app_db.query(Question).filter(
            Question.version_number == questionnaire_version
        ).all()
        question_text_by_key = {row.question_key: row.question for row in question_rows}

        now = datetime.datetime.utcnow()
        for key, value in form_data_en.items():
            data_id = str(uuid.uuid4())
            answer = ", ".join(value) if isinstance(value, list) else str(value)
            question_text = question_text_by_key.get(key) or _QUESTION_TEXT_MAP.get(key, key)
            db.execute(
                text(
                    "INSERT INTO session_data_table "
                    "(session_data_id, session_id, question, answer, created_at, question_key, questionnaire_version) "
                    "VALUES (:did, :sid, :q, :a, :ts, :qkey, :version)"
                ),
                {"did": data_id, "sid": session_id, "q": question_text, "a": answer, "ts": now,
                 "qkey": key, "version": questionnaire_version},
            )
            now = now + datetime.timedelta(seconds=1)

        db.execute(
            text(
                "UPDATE session_table SET session_end_time = :end, snehita_lifetime_risk = :risk, risk_category = :cat WHERE session_id = :sid"
            ),
            {"end": datetime.datetime.utcnow(),
             "risk": str(risk_decimal) if risk_percentage is not None else None,
             "cat": risk_cat, "sid": session_id},
        )
        db.commit()

        return {
            "success": True,
            "message": "Questionnaire submitted successfully!",
            "questionnaireVersion": questionnaire_version,
            "riskCalculated": True,
            "riskPercentage": risk_percentage,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Error submitting questionnaire for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not save your responses. Please try submitting again.",
        )
    finally:
        if 'lock_connection' in locals() and lock_connection is not None:
            try:
                if lock_name:
                    lock_connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
            finally:
                lock_connection.close()
