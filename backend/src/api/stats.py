import logging
import re
import urllib.request
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import case, func, or_, text
from ..core.cache import cached
from ..db.session import get_questionnaire_db, get_db
from ..models.models import Hospital, DoctorAssessment, Attachment
from ..mammogram_service import (
    INSTITUTE_QUESTIONS,
    MAMMOGRAM_VIEW_TYPES,
    REPORT_FILE_TYPES,
    excluded_hospital_names,
    get_mammogram_by_hospital,
    get_scored_sessions,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PINCODE_COORDS = {
    "636007": (11.6687, 78.1543, "Salem"),
    "562160": (12.6324, 77.1836, "Ramanagara"),
    "570004": (12.2959, 76.6479, "Mysuru"),
    "533201": (16.5776, 81.9974, "Amalapuram"),
    "532484": (18.3969, 83.8450, "Srikakulam"),
    "636004": (11.6804, 78.1371, "Salem"),
    "500063": (17.4062, 78.4738, "Hyderabad"),
}

_geocode_cache = {}


def _geocode_pincode(pincode, state=""):
    if pincode in PINCODE_COORDS:
        return PINCODE_COORDS[pincode]
    if pincode in _geocode_cache:
        return _geocode_cache[pincode]
    try:
        query = urllib.request.quote(f"{pincode}, {state}, India" if state else f"{pincode}, India")
        url = f"https://nominatim.openstreetmap.org/search?q={query}&format=json&limit=1&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "BCD-Portal/1.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        if data:
            addr = data[0].get("address", {})
            city = addr.get("city") or addr.get("town") or addr.get("county") or addr.get("state_district", "")
            result = (float(data[0]["lat"]), float(data[0]["lon"]), city)
            _geocode_cache[pincode] = result
            return result
    except Exception as e:
        logger.warning("Geocode failed for pincode %s: %s", pincode, e)
    return None

AGE_QUESTIONS = ('What is your current age? (Please enter a number - years)', 'Q1')
AGE_BANDS = [
    (18, 29, '18-29'), (30, 39, '30-39'), (40, 49, '40-49'),
    (50, 59, '50-59'), (60, 69, '60-69'), (0, float("inf"), '70+'),
]
RISK_NAMES = ("Baseline Risk", "Evident Risk", "Significant Risk", "High Risk")
MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
QUALIFYING_DICOM_TYPES = MAMMOGRAM_VIEW_TYPES


def _age_group(answer) -> str:
    """Age band of a questionnaire answer, reading it the way MySQL's
    CAST(... AS UNSIGNED) does: leading digits, anything else counts as 0."""
    match = re.match(r"\s*([+-]?\d+)", answer or "")
    age = int(match.group(1)) if match else 0
    if age < 0:
        age = float("inf")  # MySQL turns a negative into a huge unsigned number
    for low, high, label in AGE_BANDS:
        if low <= age <= high:
            return label
    return AGE_BANDS[-1][2]


def _bucket_counts(rows, key) -> dict:
    """Count scored sessions per key(row), split by risk bucket."""
    counts = {}
    for row in rows:
        entry = counts.setdefault(key(row), [0, 0, 0, 0])
        entry[row[5]] += 1
    return counts


@router.get("/")
def get_stats(
    db: Session = Depends(get_questionnaire_db),
    app_db: Session = Depends(get_db),
):
    return cached("stats", lambda: _compute_stats(db, app_db))


def _compute_stats(db: Session, app_db: Session):
    hospital_rows = app_db.query(Hospital.id, Hospital.name, Hospital.short_name, Hospital.state).filter(
        ~Hospital.name.in_(excluded_hospital_names(app_db))
    ).all()
    valid_hospitals = [h.name for h in hospital_rows]
    valid_hospital_ids = [h.id for h in hospital_rows]
    hospital_short_names = {h.name: h.short_name or h.name for h in hospital_rows}
    if not valid_hospitals:
        return {"totalSubjects": 0, "institutionsEmpanelled": 0, "statesCount": 0,
                "imageStudies": 0, "imageRecords": 0,
                "riskBins": [], "hospitalBins": [], "ageBins": [], "monthBins": []}

    # Every figure below comes from this one pass over the scored sessions.
    # Session-id order keeps the hospital bars in the order they have always had
    # (each hospital's first appearance in the session table).
    session_rows = sorted(get_scored_sessions(db, valid_hospitals), key=lambda r: r[0])
    total_subjects = len(session_rows)

    risk_totals = [0, 0, 0, 0]
    for row in session_rows:
        risk_totals[row[5]] += 1
    risk_bins = [{"name": name, "value": risk_totals[i]} for i, name in enumerate(RISK_NAMES)]

    by_institute = _bucket_counts(session_rows, key=lambda r: r[4])
    mammo_by_hospital_name = {
        entry["hospital_name"]: entry
        for entry in get_mammogram_by_hospital(
            app_db, db, {institute: sum(counts) for institute, counts in by_institute.items()}
        )
    }

    hospital_bins = []
    for institute_name, counts in by_institute.items():
        mammo_entry = mammo_by_hospital_name.get(institute_name, {})
        hospital_bins.append({
            "name": hospital_short_names.get(institute_name, institute_name or "Unknown"),
            "no_risk": counts[0], "low": counts[1], "moderate": counts[2], "high": counts[3],
            "assessment_count": mammo_entry.get("assessment_count", 0),
            "total_data_collections": mammo_entry.get("total_data_collections", 0),
        })

    bucket_by_session = {row[0]: row[5] for row in session_rows}
    age_counts = {label: [0, 0, 0, 0] for _, _, label in AGE_BANDS}
    age_answers = db.execute(text(
        "SELECT session_id, answer FROM session_data_table WHERE question IN :age_questions"
    ), {"age_questions": AGE_QUESTIONS}).fetchall()
    for session_id, answer in age_answers:
        if session_id in bucket_by_session:
            age_counts[_age_group(answer)][bucket_by_session[session_id]] += 1
    age_bins = [
        {"name": label, "no_risk": c[0], "low": c[1], "moderate": c[2], "high": c[3]}
        for label, c in age_counts.items()
    ]

    month_names = {}
    month_counts = {}
    for row in session_rows:
        moment = row[3] or row[2]
        if moment is None:
            continue
        sort_key = moment.strftime("%Y-%m")
        month_names[sort_key] = f"{MONTH_ABBR[moment.month - 1]} {moment.year}"
        month_counts.setdefault(sort_key, [0, 0, 0, 0])[row[5]] += 1
    month_bins = [
        {"name": month_names[k], "no_risk": c[0], "low": c[1], "moderate": c[2], "high": c[3]}
        for k, c in sorted(month_counts.items())
    ]

    institutions_empanelled = len(hospital_rows)
    states_count = len({h.state for h in hospital_rows if h.state})

    # Per assessment: it qualifies when it has all four mammogram views or any report.
    per_assessment = app_db.query(
        DoctorAssessment.patient_session_id.label("session_id"),
        func.count(func.distinct(case((Attachment.file_type.in_(QUALIFYING_DICOM_TYPES), Attachment.file_type)))).label("views"),
        func.max(case((Attachment.file_type.in_(REPORT_FILE_TYPES), 1), else_=0)).label("has_report"),
    ).outerjoin(
        Attachment, Attachment.assessment_id == DoctorAssessment.id
    ).filter(
        DoctorAssessment.hospital_id.in_(valid_hospital_ids)
    ).group_by(DoctorAssessment.id, DoctorAssessment.patient_session_id).subquery()
    image_studies, image_records = app_db.query(
        func.count(func.distinct(per_assessment.c.session_id)),
        func.count(func.distinct(case(
            (or_(per_assessment.c.views == len(QUALIFYING_DICOM_TYPES), per_assessment.c.has_report == 1),
             per_assessment.c.session_id)
        ))),
    ).one()

    return {
        "totalSubjects": total_subjects,
        "institutionsEmpanelled": institutions_empanelled,
        "statesCount": states_count,
        "imageStudies": int(image_studies or 0),
        "imageRecords": int(image_records or 0),
        "riskBins": risk_bins,
        "hospitalBins": hospital_bins,
        "ageBins": age_bins,
        "monthBins": month_bins,
    }


@router.get("/hospital-locations")
def get_hospital_locations(
    app_db: Session = Depends(get_db),
    db: Session = Depends(get_questionnaire_db),
):
    return cached("hospital-locations", lambda: _compute_hospital_locations(app_db, db))


def _compute_hospital_locations(app_db: Session, db: Session):
    hospitals = app_db.query(Hospital).filter(~Hospital.name.in_(excluded_hospital_names(app_db))).all()
    valid_names = [h.name for h in hospitals]
    if not valid_names:
        return []

    subject_rows = db.execute(text("""
        SELECT sd.answer AS institute, COUNT(DISTINCT s.session_id) AS subjects
        FROM session_table s
        JOIN session_data_table sd ON s.session_id = sd.session_id
        WHERE sd.question IN :inst_questions
          AND sd.answer IN :valid_names
          AND s.snehita_lifetime_risk IS NOT NULL
        GROUP BY sd.answer
    """), {"inst_questions": INSTITUTE_QUESTIONS, "valid_names": tuple(valid_names)}).fetchall()
    subject_counts = {r[0]: int(r[1]) for r in subject_rows}

    locations = []
    for h in hospitals:
        result = _geocode_pincode(h.pincode or "", h.state or "")
        if not result:
            continue
        city = result[2] if len(result) > 2 else ""
        locations.append({
            "id": h.id,
            "name": h.name,
            "short_name": h.short_name or h.name,
            "city": city,
            "state": h.state or "",
            "latitude": result[0],
            "longitude": result[1],
            "subjects": subject_counts.get(h.name, 0),
        })
    return locations
