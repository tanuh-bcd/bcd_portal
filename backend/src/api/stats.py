import logging
import urllib.request
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from ..db.session import get_questionnaire_db, get_db, get_pilot_deployment_db
from ..models.models import Hospital, DoctorAssessment
from ..core.pilot_study import is_pilot_study_hospital
from ..mammogram_service import (
    get_mammogram_by_hospital,
    get_pilot_deployment_risk_counts,
    get_pilot_deployment_submission_counts,
    get_pilot_deployment_age_bins,
    get_pilot_deployment_month_bins,
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

INSTITUTE_QUESTIONS = (
    'Institute Name',
    'Institute Name:',
    'Enter the Hospital ID(If any, else leave):',
    'Enter the Institution Name (if any, else leave)',
    'Enter the Institution Name (If any, else leave)',
    'Q45',
)
AGE_QUESTIONS = ('What is your current age? (Please enter a number - years)', 'Q1')


def _get_institute_filter(valid_names):
    return f"""
    JOIN (
        SELECT session_id, MAX(answer) as answer
        FROM session_data_table
        WHERE question IN :inst_questions
          AND answer IN :valid_names
        GROUP BY session_id
    ) sd_inst ON s.session_id = sd_inst.session_id
    """

QUALIFYING_DICOM_TYPES = ('mammo_cc_left', 'mammo_cc_right', 'mammo_mlo_left', 'mammo_mlo_right')

def _has_qualifying_images(assessment):
    att_types = {att.file_type for att in assessment.attachments}
    all_4_dicom = all(t in att_types for t in QUALIFYING_DICOM_TYPES)
    return all_4_dicom or 'mammo_reading' in att_types or 'us_reading' in att_types

RISK_CASE = """
    SUM(CASE WHEN s.snehita_lifetime_risk < 0.4004 THEN 1 ELSE 0 END) as no_risk,
    SUM(CASE WHEN s.snehita_lifetime_risk >= 0.4004 AND s.snehita_lifetime_risk < 0.574 THEN 1 ELSE 0 END) as low_risk,
    SUM(CASE WHEN s.snehita_lifetime_risk >= 0.574 AND s.snehita_lifetime_risk < 0.795 THEN 1 ELSE 0 END) as moderate_risk,
    SUM(CASE WHEN s.snehita_lifetime_risk >= 0.795 THEN 1 ELSE 0 END) as high_risk
"""


@router.get("/")
def get_stats(
    db: Session = Depends(get_questionnaire_db),
    app_db: Session = Depends(get_db),
    pilot_db: Session = Depends(get_pilot_deployment_db),
):
    EXCLUDED_NAMES = ('Test', 'Tanuh Foundation', 'Pilot Study -Test')
    hospital_rows = app_db.query(Hospital.id, Hospital.name, Hospital.short_name).filter(
        ~Hospital.name.in_(EXCLUDED_NAMES)
    ).all()
    valid_hospitals = [h.name for h in hospital_rows]
    valid_hospital_ids = [h.id for h in hospital_rows]
    hospital_base_short_names = {h.name: h.short_name or h.name for h in hospital_rows}
    hospital_short_names = {
        name: (f'PS-{short}' if is_pilot_study_hospital(name) else short)
        for name, short in hospital_base_short_names.items()
    }
    if not valid_hospitals:
        return {"totalSubjects": 0, "institutionsEmpanelled": 0, "statesCount": 0,
                "imageStudies": 0, "imageRecords": 0,
                "riskBins": [], "hospitalBins": [], "ageBins": [], "monthBins": []}

    inst_filter = _get_institute_filter(valid_hospitals)
    params = {"inst_questions": INSTITUTE_QUESTIONS, "valid_names": tuple(valid_hospitals)}

    total_res = db.execute(text(f"""
        SELECT COUNT(DISTINCT s.session_id) as total
        FROM session_table s {inst_filter}
        WHERE s.snehita_lifetime_risk IS NOT NULL
    """), params).fetchone()
    total_subjects = total_res[0] if total_res else 0

    risk_res = db.execute(text(f"""
        SELECT {RISK_CASE}
        FROM session_table s {inst_filter}
        WHERE s.snehita_lifetime_risk IS NOT NULL
    """), params).fetchone()

    risk_bins = [
        {"name": "Baseline Risk", "value": int(risk_res[0] or 0)},
        {"name": "Evident Risk", "value": int(risk_res[1] or 0)},
        {"name": "Significant Risk", "value": int(risk_res[2] or 0)},
        {"name": "High Risk", "value": int(risk_res[3] or 0)},
    ] if risk_res else []

    hosp_rows = db.execute(text(f"""
        SELECT sd_inst.answer as institute,
            SUM(CASE WHEN s.snehita_lifetime_risk < 0.4004 THEN 1 ELSE 0 END) as no_risk,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.4004 AND s.snehita_lifetime_risk < 0.574 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.574 AND s.snehita_lifetime_risk < 0.795 THEN 1 ELSE 0 END) as moderate,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.795 THEN 1 ELSE 0 END) as high
        FROM session_table s {inst_filter}
        WHERE s.snehita_lifetime_risk IS NOT NULL
        GROUP BY sd_inst.answer
    """), params).fetchall()

    mammo_by_hospital_name = {
        entry["hospital_name"]: entry for entry in get_mammogram_by_hospital(app_db, db, pilot_db)
    }

    hospital_bins_raw = []
    for r in hosp_rows:
        institute_name = r[0]
        mammo_entry = mammo_by_hospital_name.get(institute_name, {})
        hospital_bins_raw.append({
            "name": hospital_short_names.get(institute_name, institute_name or "Unknown"),
            "no_risk": int(r[1] or 0), "low": int(r[2] or 0), "moderate": int(r[3] or 0), "high": int(r[4] or 0),
            "is_pilot_study": is_pilot_study_hospital(institute_name),
            "pilot_study_submitted": mammo_entry.get("pilot_deployment_submitted", 0),
            "assessment_count": mammo_entry.get("assessment_count", 0),
            "total_data_collections": mammo_entry.get("total_data_collections", 0),
            "_is_pilot": is_pilot_study_hospital(institute_name),
            "_base_key": (hospital_base_short_names.get(institute_name, institute_name) or "").strip().lower(),
        })

    # Pilot-study institutes with no bcd_questionnaire session of their own
    # (e.g. "Pilot Study - SMSIMSR") have no row above at all. Synthesize one
    # from the pilot_deployment schema's own completed submissions so the
    # institute still shows up here: LOW_RISK -> no_risk/Baseline, HIGH_RISK
    # -> high. Submissions with no completed result yet don't count (they're
    # not "submitted" for this purpose, matching pilot_study_submitted).
    existing_institute_names = {r[0] for r in hosp_rows}
    pilot_risk_counts = get_pilot_deployment_risk_counts(pilot_db)
    for hospital_name in valid_hospitals:
        if hospital_name in existing_institute_names or not is_pilot_study_hospital(hospital_name):
            continue
        risk = pilot_risk_counts.get(hospital_name)
        if not risk or (risk["low_risk"] == 0 and risk["high_risk"] == 0):
            continue
        mammo_entry = mammo_by_hospital_name.get(hospital_name, {})
        hospital_bins_raw.append({
            "name": hospital_short_names.get(hospital_name, hospital_name),
            "no_risk": risk["low_risk"], "low": 0, "moderate": 0, "high": risk["high_risk"],
            "is_pilot_study": True,
            "pilot_study_submitted": mammo_entry.get("pilot_deployment_submitted", 0),
            "assessment_count": mammo_entry.get("assessment_count", 0),
            "total_data_collections": mammo_entry.get("total_data_collections", 0),
            "_is_pilot": True,
            "_base_key": (hospital_base_short_names.get(hospital_name, hospital_name) or "").strip().lower(),
        })

    # Keep each pilot-study institute's bar immediately next to its real
    # counterpart (same base short name) rather than wherever it happens to
    # fall in query/group order.
    pilot_by_base = {}
    for entry in hospital_bins_raw:
        if entry["_is_pilot"]:
            pilot_by_base.setdefault(entry["_base_key"], []).append(entry)

    hospital_bins = []
    for entry in hospital_bins_raw:
        if entry["_is_pilot"]:
            continue
        hospital_bins.append(entry)
        for pilot_entry in pilot_by_base.pop(entry["_base_key"], []):
            hospital_bins.append(pilot_entry)
    for leftovers in pilot_by_base.values():
        hospital_bins.extend(leftovers)

    for entry in hospital_bins:
        entry.pop("_is_pilot", None)
        entry.pop("_base_key", None)

    age_rows = db.execute(text(f"""
        SELECT
            CASE
                WHEN CAST(sd_age.answer AS UNSIGNED) BETWEEN 18 AND 29 THEN '18-29'
                WHEN CAST(sd_age.answer AS UNSIGNED) BETWEEN 30 AND 39 THEN '30-39'
                WHEN CAST(sd_age.answer AS UNSIGNED) BETWEEN 40 AND 49 THEN '40-49'
                WHEN CAST(sd_age.answer AS UNSIGNED) BETWEEN 50 AND 59 THEN '50-59'
                WHEN CAST(sd_age.answer AS UNSIGNED) BETWEEN 60 AND 69 THEN '60-69'
                ELSE '70+'
            END as age_group,
            SUM(CASE WHEN s.snehita_lifetime_risk < 0.4004 THEN 1 ELSE 0 END) as no_risk,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.4004 AND s.snehita_lifetime_risk < 0.574 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.574 AND s.snehita_lifetime_risk < 0.795 THEN 1 ELSE 0 END) as moderate,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.795 THEN 1 ELSE 0 END) as high
        FROM session_table s
        JOIN session_data_table sd_age ON s.session_id = sd_age.session_id
        {inst_filter}
        WHERE s.snehita_lifetime_risk IS NOT NULL
          AND sd_age.question IN :age_questions
        GROUP BY age_group
        ORDER BY age_group ASC
    """), {**params, "age_questions": AGE_QUESTIONS}).fetchall()

    age_labels = ['18-29', '30-39', '40-49', '50-59', '60-69', '70+']
    age_map = {r[0]: r for r in age_rows}
    age_bins = [
        {"name": label, "no_risk": int(age_map[label][1] or 0) if label in age_map else 0,
         "low": int(age_map[label][2] or 0) if label in age_map else 0,
         "moderate": int(age_map[label][3] or 0) if label in age_map else 0,
         "high": int(age_map[label][4] or 0) if label in age_map else 0}
        for label in age_labels
    ]

    # Fold in pilot_deployment's completed submissions (binary risk model:
    # LOW_RISK -> no_risk, HIGH_RISK -> high) so pilot-study subjects count
    # toward the same aggregate age distribution as everyone else.
    pilot_age_bins = get_pilot_deployment_age_bins(pilot_db)
    for bin_entry in age_bins:
        pilot_bin = pilot_age_bins.get(bin_entry["name"])
        if pilot_bin:
            bin_entry["no_risk"] += pilot_bin["no_risk"]
            bin_entry["high"] += pilot_bin["high"]

    month_rows = db.execute(text(f"""
        SELECT
            DATE_FORMAT(COALESCE(s.session_end_time, s.session_start_time), '%b %Y') as month_year,
            DATE_FORMAT(COALESCE(s.session_end_time, s.session_start_time), '%Y-%m') as sort_key,
            SUM(CASE WHEN s.snehita_lifetime_risk < 0.4004 THEN 1 ELSE 0 END) as no_risk,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.4004 AND s.snehita_lifetime_risk < 0.574 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.574 AND s.snehita_lifetime_risk < 0.795 THEN 1 ELSE 0 END) as moderate,
            SUM(CASE WHEN s.snehita_lifetime_risk >= 0.795 THEN 1 ELSE 0 END) as high
        FROM session_table s {inst_filter}
        WHERE s.snehita_lifetime_risk IS NOT NULL
        GROUP BY month_year, sort_key
        ORDER BY sort_key ASC
    """), params).fetchall()

    month_map = {
        r[1]: {"name": r[0], "no_risk": int(r[2] or 0), "low": int(r[3] or 0), "moderate": int(r[4] or 0), "high": int(r[5] or 0)}
        for r in month_rows
    }

    # Same fold-in for Month-wise Distribution; a month with pilot data but
    # no bcd_questionnaire sessions yet gets its own new entry.
    pilot_month_bins = get_pilot_deployment_month_bins(pilot_db)
    for sort_key, pilot_bin in pilot_month_bins.items():
        entry = month_map.setdefault(
            sort_key, {"name": pilot_bin["name"], "no_risk": 0, "low": 0, "moderate": 0, "high": 0}
        )
        entry["no_risk"] += pilot_bin["no_risk"]
        entry["high"] += pilot_bin["high"]

    month_bins = [month_map[k] for k in sorted(month_map.keys())]

    inst_res = app_db.execute(text(
        "SELECT COUNT(*) FROM hospitals WHERE name NOT IN ('Test', 'Tanuh Foundation', 'Pilot Study -Test')"
    )).fetchone()
    institutions_empanelled = inst_res[0] if inst_res else 0

    states_res = app_db.execute(text(
        "SELECT COUNT(DISTINCT state) FROM hospitals WHERE name NOT IN ('Test', 'Tanuh Foundation', 'Pilot Study -Test') AND state IS NOT NULL AND state != ''"
    )).fetchone()
    states_count = states_res[0] if states_res else 0

    assessments = app_db.query(DoctorAssessment).filter(
        DoctorAssessment.hospital_id.in_(valid_hospital_ids)
    ).options(joinedload(DoctorAssessment.attachments)).all()

    image_studies = len({a.patient_session_id for a in assessments})
    image_records = len({a.patient_session_id for a in assessments if _has_qualifying_images(a)})

    return {
        "totalSubjects": total_subjects,
        "institutionsEmpanelled": institutions_empanelled,
        "statesCount": states_count,
        "imageStudies": image_studies,
        "imageRecords": image_records,
        "riskBins": risk_bins,
        "hospitalBins": hospital_bins,
        "ageBins": age_bins,
        "monthBins": month_bins,
    }


@router.get("/hospital-locations")
def get_hospital_locations(
    app_db: Session = Depends(get_db),
    db: Session = Depends(get_questionnaire_db),
    pilot_db: Session = Depends(get_pilot_deployment_db),
):
    EXCLUDED = ("Test", "Tanuh Foundation", "Pilot Study -Test")
    hospitals = app_db.query(Hospital).filter(~Hospital.name.in_(EXCLUDED)).all()
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
    pilot_submission_counts = get_pilot_deployment_submission_counts(pilot_db)

    def _submitted(hospital_name: str) -> int:
        return subject_counts.get(hospital_name, 0) + pilot_submission_counts.get(hospital_name, 0)

    # A pilot-study hospital row (e.g. "Pilot Study - SMSIMSR") and its real
    # counterpart ("Sri Madhusudan...") are the same physical institute, just
    # two separate hospital records sharing one short_name -- group by that
    # so the map shows one pin/institute, not two.
    groups = {}
    for h in hospitals:
        key = (h.short_name or h.name or "").strip().lower()
        groups.setdefault(key, []).append(h)

    locations = []
    for group in groups.values():
        primary = next((h for h in group if not is_pilot_study_hospital(h.name)), group[0])
        pilot_siblings = [h for h in group if h is not primary]

        result = _geocode_pincode(primary.pincode or "", primary.state or "")
        if not result:
            for sibling in pilot_siblings:
                result = _geocode_pincode(sibling.pincode or "", sibling.state or "")
                if result:
                    break
        if not result:
            continue
        city = result[2] if len(result) > 2 else ""

        name = primary.name
        subjects_total = _submitted(primary.name)
        for sibling in pilot_siblings:
            subjects_total += _submitted(sibling.name)
            name = f"{name} (Pilot Study - {sibling.short_name or sibling.name})"

        locations.append({
            "id": primary.id,
            "name": name,
            "short_name": primary.short_name or primary.name,
            "city": city,
            "state": primary.state or "",
            "latitude": result[0],
            "longitude": result[1],
            "subjects": subjects_total,
        })
    return locations
