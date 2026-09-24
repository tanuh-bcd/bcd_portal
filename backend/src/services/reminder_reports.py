import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, func, text
from sqlalchemy.orm import Session, joinedload

from ..core.config import settings
from ..core.email import send_template_email
from ..models.models import DoctorAssessment, Hospital, ReminderEmailLog, ReminderDelivery

logger = logging.getLogger(__name__)

TEMPLATE_KEY = "fortnightly_submission_update"
INSTITUTE_QUESTIONS = (
    "Institute Name",
    "Institute Name:",
    "Enter the Hospital ID(If any, else leave):",
    "Q45",
)
MAMMOGRAM_VIEWS = {
    "mammo_cc_left",
    "mammo_cc_right",
    "mammo_mlo_left",
    "mammo_mlo_right",
}


@dataclass(frozen=True)
class ReminderReport:
    hospital_id: str
    hospital_name: str
    contact_person: str
    recipient_email: str
    report_date: date
    collection_start_date: Optional[date]
    quarter_start: date
    quarter_end: date
    data_points: int
    assessments_submitted: int
    mammography_cases: int
    pending_submissions: int
    assessment_backlog: int
    quarterly_target: int
    missing_questionnaire_sessions: int
    incomplete_assessments: int
    missing_mammogram_views: int
    missing_mammogram_reports: int
    mammogram_quality_flags: int
    reports_uploaded: int = 0
    image_records: int = 0
    image_studies: int = 0
    month_counts: dict = field(default_factory=dict)
    month_risk_counts: dict = field(default_factory=dict)


def current_date() -> date:
    return datetime.now(ZoneInfo(settings.REMINDER_TIMEZONE)).date()


def quarter_bounds(report_date: date) -> tuple[date, date]:
    start_month = ((report_date.month - 1) // 3) * 3 + 1
    start = date(report_date.year, start_month, 1)
    if start_month == 10:
        end = date(report_date.year + 1, 1, 1)
    else:
        end = date(report_date.year, start_month + 3, 1)
    return start, end


def build_report(
    db: Session,
    questionnaire_db: Session,
    hospital: Hospital,
    report_date: date,
    target: Optional[int] = None,
) -> ReminderReport:
    # ``target`` is retained only so older callers do not break. The hospital
    # update is now a cumulative contribution summary, not a target reminder.
    target = 0
    quarter_start, quarter_end = quarter_bounds(report_date)
    report_end = report_date + timedelta(days=1)

    session_rows = questionnaire_db.execute(text("""
        SELECT s.session_id,
               MIN(COALESCE(s.session_end_time, s.session_start_time)) AS collected_at,
               MAX(s.snehita_lifetime_risk) AS risk
        FROM session_table s
        JOIN session_data_table sd ON s.session_id = sd.session_id
        WHERE sd.question IN ('Institute Name', 'Institute Name:',
                              'Enter the Hospital ID(If any, else leave):', 'Q45')
          AND sd.answer = :hospital_name
          AND s.snehita_lifetime_risk IS NOT NULL
          AND COALESCE(s.session_end_time, s.session_start_time) < :report_end
        GROUP BY s.session_id
    """), {
        "hospital_name": hospital.name,
        "report_end": report_end,
    }).fetchall()
    session_ids = [row[0] for row in session_rows]
    data_points = len(session_ids)
    collection_dates = [row[1] for row in session_rows if row[1] is not None]
    first_collection = min(collection_dates) if collection_dates else None
    if isinstance(first_collection, datetime):
        collection_start_date = first_collection.date()
    elif isinstance(first_collection, date):
        collection_start_date = first_collection
    elif first_collection:
        collection_start_date = datetime.fromisoformat(str(first_collection)).date()
    else:
        collection_start_date = None

    assessments = []
    missing_questionnaire_sessions = 0
    if session_ids:
        assessments = db.query(DoctorAssessment).options(
            joinedload(DoctorAssessment.attachments)
        ).filter(
            DoctorAssessment.patient_session_id.in_(session_ids),
            DoctorAssessment.hospital_id == hospital.id,
            DoctorAssessment.created_at < report_end,
        ).all()

        missing_query = text("""
            SELECT COUNT(DISTINCT session_id)
            FROM session_data_table
            WHERE session_id IN :session_ids
              AND (answer IS NULL OR TRIM(answer) = '')
        """).bindparams(bindparam("session_ids", expanding=True))
        missing_questionnaire_sessions = questionnaire_db.execute(
            missing_query, {"session_ids": session_ids}
        ).scalar() or 0

    incomplete_assessments = 0
    missing_mammogram_views = 0
    missing_mammogram_reports = 0
    mammogram_quality_flags = 0
    mammography_cases = 0
    complete_mammogram_cases = 0
    mammogram_report_cases = 0
    for assessment in assessments:
        attachment_types = {attachment.file_type for attachment in assessment.attachments}
        if MAMMOGRAM_VIEWS.intersection(attachment_types):
            mammography_cases += 1
        if not assessment.mammo_birads or not assessment.mammo_density or not assessment.clinical_findings:
            incomplete_assessments += 1
        if not MAMMOGRAM_VIEWS.issubset(attachment_types):
            missing_mammogram_views += 1
        else:
            complete_mammogram_cases += 1
        if "mammo_reading" not in attachment_types:
            missing_mammogram_reports += 1
        else:
            mammogram_report_cases += 1
        if not assessment.routine_views_uploaded:
            mammogram_quality_flags += 1

    # Pending imaging is measured across every collected record, including
    # records for which a clinician assessment has not yet been created.
    missing_mammogram_views = max(data_points - complete_mammogram_cases, 0)
    missing_mammogram_reports = max(data_points - mammogram_report_cases, 0)

    month_counts = {}
    month_risk_counts = {}
    for row in session_rows:
        if row[1] is not None:
            month = str(row[1])[:7]
            month_counts[month] = month_counts.get(month, 0) + 1
            risk = float(row[2])
            bucket = 0 if risk < 0.4004 else 1 if risk < 0.574 else 2 if risk < 0.795 else 3
            month_risk_counts.setdefault(month, [0, 0, 0, 0])[bucket] += 1
    image_records = reports_uploaded = 0
    image_subjects = set()
    for assessment in assessments:
        for attachment in assessment.attachments:
            if attachment.created_at and attachment.created_at.date() >= report_end:
                continue
            if attachment.file_type in MAMMOGRAM_VIEWS or attachment.file_type == "mammo_dicom":
                image_records += 1
                image_subjects.add(assessment.patient_session_id)
            elif attachment.file_type == "mammo_reading":
                reports_uploaded += 1

    return ReminderReport(
        reports_uploaded=reports_uploaded,
        image_records=image_records,
        image_studies=len(image_subjects),
        month_counts=dict(sorted(month_counts.items())),
        month_risk_counts=month_risk_counts,
        hospital_id=hospital.id,
        hospital_name=hospital.name,
        contact_person=hospital.contact_person or "Hospital Team",
        recipient_email=settings.REMINDER_RECIPIENT_EMAIL or hospital.email,
        report_date=report_date,
        collection_start_date=collection_start_date,
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        data_points=int(data_points),
        assessments_submitted=len(assessments),
        mammography_cases=mammography_cases,
        pending_submissions=max(target - int(data_points), 0),
        assessment_backlog=max(int(data_points) - len(assessments), 0),
        quarterly_target=target,
        missing_questionnaire_sessions=int(missing_questionnaire_sessions),
        incomplete_assessments=incomplete_assessments,
        missing_mammogram_views=missing_mammogram_views,
        missing_mammogram_reports=missing_mammogram_reports,
        mammogram_quality_flags=mammogram_quality_flags,
    )


def is_due(db: Session, hospital_id: str, report_date: date, interval_days: int) -> bool:
    last_sent = db.query(func.max(ReminderEmailLog.sent_at)).filter(
        ReminderEmailLog.hospital_id == hospital_id,
        ReminderEmailLog.status == "sent",
    ).scalar()
    if not last_sent:
        return True
    return last_sent.date() <= report_date - timedelta(days=interval_days)


def report_variables(report: ReminderReport) -> dict:
    return {
        "contact_name": report.contact_person,
        "hospital_name": report.hospital_name,
        "collection_start_date": (
            report.collection_start_date.strftime("%d %B %Y")
            if report.collection_start_date else "Not started"
        ),
        "data_points": report.data_points,
        "assessments_submitted": report.assessments_submitted,
        "assessments_pending": report.assessment_backlog,
        "mammogram_images_pending": report.missing_mammogram_views,
        "mammogram_reports_pending": report.missing_mammogram_reports,
        "portal_url": settings.REMINDER_PORTAL_URL,
        "support_email": settings.REMINDER_SUPPORT_EMAIL,
    }


def send_report(db: Session, report: ReminderReport, dry_run: bool = False) -> ReminderEmailLog:
    existing = db.query(ReminderEmailLog).filter(
        ReminderEmailLog.hospital_id == report.hospital_id,
        ReminderEmailLog.report_date == report.report_date,
    ).first()
    if existing and existing.status == "sent":
        return existing

    log = existing or ReminderEmailLog(
        hospital_id=report.hospital_id,
        recipient_email=report.recipient_email,
        report_date=report.report_date,
        quarter_start=report.quarter_start,
        quarter_end=report.quarter_end,
        data_points=report.data_points,
        assessments_submitted=report.assessments_submitted,
        pending_submissions=report.pending_submissions,
        quarterly_target=report.quarterly_target,
        missing_questionnaire_sessions=report.missing_questionnaire_sessions,
        incomplete_assessments=report.incomplete_assessments,
        missing_mammogram_views=report.missing_mammogram_views,
        missing_mammogram_reports=report.missing_mammogram_reports,
        mammogram_quality_flags=report.mammogram_quality_flags,
        status="pending",
    )
    if not existing:
        db.add(log)
    else:
        log.recipient_email = report.recipient_email
        log.quarter_start = report.quarter_start
        log.quarter_end = report.quarter_end
        log.data_points = report.data_points
        log.assessments_submitted = report.assessments_submitted
        log.pending_submissions = report.pending_submissions
        log.quarterly_target = report.quarterly_target
        log.missing_questionnaire_sessions = report.missing_questionnaire_sessions
        log.incomplete_assessments = report.incomplete_assessments
        log.missing_mammogram_views = report.missing_mammogram_views
        log.missing_mammogram_reports = report.missing_mammogram_reports
        log.mammogram_quality_flags = report.mammogram_quality_flags

    if dry_run:
        log.status = "dry_run"
        db.commit()
        db.refresh(log)
        return log

    try:
        send_template_email(
            db,
            TEMPLATE_KEY,
            report.recipient_email,
            report_variables(report),
            reply_to=settings.REMINDER_REPLY_TO,
            raise_on_error=True,
        )
        log.status = "sent"
        log.sent_at = datetime.now(ZoneInfo(settings.REMINDER_TIMEZONE)).replace(tzinfo=None)
        log.error_message = None
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)[:2000]
        logger.exception("Reminder email failed for hospital %s", report.hospital_id)

    db.commit()
    db.refresh(log)
    return log


def run_reminders(
    db: Session,
    questionnaire_db: Session,
    report_date: Optional[date] = None,
    hospital_id: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> List[ReminderDelivery]:
    from .reminder_delivery import run_dashboard_reminders
    return run_dashboard_reminders(db, questionnaire_db, report_date or current_date(),
                                   hospital_id, dry_run, force)
