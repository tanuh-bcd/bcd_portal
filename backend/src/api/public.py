import math
import json
import uuid
import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db.session import get_questionnaire_db
from ..core.config import settings
from google.cloud import storage
from pydantic import BaseModel
from typing import Any, Dict, Optional

router = APIRouter()

_questionnaire_json_path = Path(__file__).resolve().parent / "questionnaire_en.json"
_QUESTION_TEXT_MAP: Dict[str, str] = {}
if _questionnaire_json_path.exists():
    with open(_questionnaire_json_path, encoding="utf-8") as _f:
        _QUESTION_TEXT_MAP = {k: v.get("question", k) for k, v in json.load(_f).get("questions", {}).items()}


def calculate_snehitha_risk(form_data: dict) -> str:
    age = int(form_data.get("Q1", 0) or 0)
    age_at_menarche = int(form_data.get("Q10", 0) or 0)
    irregular_cycles = 1 if form_data.get("Q12_Current") == "No" else 0
    breastfeeding_24m = 1 if form_data.get("Q17") == "greater than 24 months" else 0
    first_degree_relatives = 1 if form_data.get("Q21") == "First Order (Mother, Sibling, Father)" else 0
    previous_biopsy = 1 if form_data.get("Q40") == "Yes" else 0

    is_nullipara = form_data.get("Q14") == "No"
    age_first_birth_25_29 = form_data.get("Q16") == "25 to 29"
    age_first_birth_gte30 = form_data.get("Q16") == "After 30"

    age_first_live_birth_2529_or_nullipara = 1 if (is_nullipara or age_first_birth_25_29) else 0
    age_first_live_birth_30_or_more = 1 if age_first_birth_gte30 else 0

    logit_p = (
        -0.940
        + (0.027 * age)
        - (0.082 * age_at_menarche)
        + (0.453 * irregular_cycles)
        - (0.892 * breastfeeding_24m)
        + (0.810 * first_degree_relatives)
        + (1.420 * previous_biopsy)
        + (0.811 * age_first_live_birth_2529_or_nullipara)
        + (1.035 * age_first_live_birth_30_or_more)
    )

    probability = 1 / (1 + math.exp(-logit_p))
    risk_percentage = round(probability * 100, 2)
    if math.isnan(risk_percentage):
        risk_percentage = 0.00
    return str(risk_percentage)


@router.post("/session/start")
def start_session(request: Request, db: Session = Depends(get_questionnaire_db)):
    session_id = str(uuid.uuid4())
    ip_address = request.client.host if request.client else "unknown"
    now = datetime.datetime.utcnow()

    db.execute(
        text("INSERT INTO session_table (session_id, ip_address, session_start_time) VALUES (:sid, :ip, :ts)"),
        {"sid": session_id, "ip": ip_address, "ts": now},
    )
    db.commit()
    return {"success": True, "sessionId": session_id}


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

    if settings.GOOGLE_APPLICATION_CREDENTIALS and settings.GOOGLE_APPLICATION_CREDENTIALS.strip():
        client = storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
    else:
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


@router.post("/submit")
def submit_questionnaire(payload: SubmitPayload, db: Session = Depends(get_questionnaire_db)):
    session_id = payload.sessionId
    form_data_en = payload.formDataEn

    if not session_id or not form_data_en:
        raise HTTPException(status_code=400, detail="Session ID and form data are required.")

    risk_percentage = calculate_snehitha_risk(form_data_en)

    now = datetime.datetime.utcnow()
    for key, value in form_data_en.items():
        data_id = str(uuid.uuid4())
        answer = ", ".join(value) if isinstance(value, list) else str(value)
        question_text = _QUESTION_TEXT_MAP.get(key, key)
        db.execute(
            text(
                "INSERT INTO session_data_table (session_data_id, session_id, question, answer, created_at) "
                "VALUES (:did, :sid, :q, :a, :ts)"
            ),
            {"did": data_id, "sid": session_id, "q": question_text, "a": answer, "ts": now},
        )
        now = now + datetime.timedelta(seconds=1)

    risk_decimal = round(float(risk_percentage) / 100, 2)
    if risk_decimal < 0.4004:
        risk_cat = "Baseline Risk"
    elif risk_decimal < 0.574:
        risk_cat = "Evident Risk"
    elif risk_decimal < 0.795:
        risk_cat = "Significant Risk"
    else:
        risk_cat = "High Risk"

    db.execute(
        text(
            "UPDATE session_table SET session_end_time = :end, snehita_lifetime_risk = :risk, risk_category = :cat WHERE session_id = :sid"
        ),
        {"end": datetime.datetime.utcnow(), "risk": str(risk_decimal), "cat": risk_cat, "sid": session_id},
    )
    db.commit()

    return {"success": True, "message": "Questionnaire submitted successfully!", "riskPercentage": risk_percentage}
