from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import get_current_user
from ..core.config import settings
from ..db.session import QuestionnaireSessionLocal, get_db, get_questionnaire_db
from ..models.models import User
from ..services.reminder_reports import (
    aggregate_recipients,
    build_reports,
    current_date,
    is_delivery_disabled,
    is_delivery_paused,
    run_reminders,
    reminder_cc_recipients,
    set_delivery_disabled,
    set_delivery_paused,
)

router = APIRouter()


def verify_scheduler_oidc(authorization: str = Header(default="")) -> dict:
    if not settings.CRON_OIDC_AUDIENCE or not settings.CRON_SERVICE_ACCOUNT_EMAIL:
        raise HTTPException(status_code=503, detail="Reminder scheduler authentication is not configured")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.CRON_OIDC_AUDIENCE
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid scheduler identity") from exc
    if not claims.get("email_verified") or claims.get("email", "").lower() != settings.CRON_SERVICE_ACCOUNT_EMAIL.lower():
        raise HTTPException(status_code=403, detail="Scheduler identity is not authorised")
    return claims


@router.post("/run", dependencies=[Depends(verify_scheduler_oidc)])
def run_due_hospital_reminders(db: Session = Depends(get_db)):
    if not settings.REMINDER_EMAIL_ENABLED:
        raise HTTPException(status_code=503, detail="Reminder delivery is disabled")
    lock_acquired = True
    if db.bind.dialect.name == "mysql":
        lock_acquired = db.execute(text("SELECT GET_LOCK('pinkshield_reminders', 0)")).scalar() == 1
    if not lock_acquired:
        raise HTTPException(status_code=409, detail="Another reminder run is active")
    questionnaire_db = QuestionnaireSessionLocal()
    try:
        results = run_reminders(db, questionnaire_db)
        return {"status": "completed", "processed_recipient_deliveries": len(results)}
    finally:
        questionnaire_db.close()
        if db.bind.dialect.name == "mysql":
            db.execute(text("SELECT RELEASE_LOCK('pinkshield_reminders')"))


def _configured_emails(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def require_reminder_operator(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    email = current_user.get("email", "").strip().lower()
    authorized = _configured_emails(settings.REMINDER_OPERATOR_EMAILS)
    active_user = db.query(User).filter(
        User.email == email,
        User.is_active.is_(True),
    ).first()
    if email not in authorized or not active_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage reminder reports",
        )
    return current_user


def _report_preview(report) -> dict:
    return {
        "hospitalId": report.hospital_id,
        "hospitalName": report.hospital_name,
        "lifetimeDataPoints": report.lifetime_data_points,
        "currentQuarterDataPoints": report.data_points,
        "assessmentsSubmitted": report.assessments_submitted,
        "pendingSubmissions": report.pending_submissions,
        "quarterlyTarget": report.quarterly_target,
        "currentQuarterRecords": report.current_quarter_records,
        "dataQuality": {
            "missingConsent": report.missing_consent,
            "missingQuestionnaire": report.missing_questionnaire_sessions,
            "blankQuestionnaireFields": report.blank_questionnaire_sessions,
            "missingMammogramViews": report.missing_mammogram_views,
            "missingBIRADS": report.missing_birads,
            "missingACRDensity": report.missing_density,
            "missingMammogramReport": report.missing_mammogram_reports,
            "routineViewQualityFlags": report.mammogram_quality_flags,
        },
        "activeRecipientCount": report.active_recipient_count,
        "activeRecipientEmails": list(report.active_recipient_emails),
        "goalAchieved": report.pending_submissions == 0,
    }


@router.get("/status")
def reminder_status(
    db: Session = Depends(get_db),
    _operator: dict = Depends(require_reminder_operator),
):
    return {
        "deliveryEnabled": settings.REMINDER_EMAIL_ENABLED,
        "disabled": is_delivery_disabled(db),
        "paused": is_delivery_paused(db),
        "intervalDays": settings.REMINDER_INTERVAL_DAYS,
        "pilotIntervalMinutes": settings.REMINDER_INTERVAL_MINUTES,
        "quarterlyTarget": settings.REMINDER_QUARTERLY_TARGET,
        "aggregateRecipients": [recipient.email for recipient in aggregate_recipients()],
        "ccRecipients": reminder_cc_recipients(),
        "maxDeliveryAttempts": max(settings.REMINDER_MAX_DELIVERY_ATTEMPTS, 1),
        "failureRecipientEmail": settings.REMINDER_FAILURE_RECIPIENT_EMAIL,
    }


@router.get("/preview")
def preview_reports(
    hospital_id: Optional[str] = Query(None),
    report_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    questionnaire_db: Session = Depends(get_questionnaire_db),
    _operator: dict = Depends(require_reminder_operator),
):
    as_of = report_date or current_date()
    reports = build_reports(db, questionnaire_db, as_of, hospital_id=hospital_id)
    if hospital_id and not reports:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {
        "reportDate": as_of,
        "reports": [_report_preview(report) for report in reports],
    }


@router.post("/resend")
def manually_resend_reports(
    hospital_id: Optional[str] = Query(None),
    include_aggregate: bool = Query(False),
    db: Session = Depends(get_db),
    questionnaire_db: Session = Depends(get_questionnaire_db),
    _operator: dict = Depends(require_reminder_operator),
):
    if not settings.REMINDER_EMAIL_ENABLED:
        raise HTTPException(status_code=503, detail="Reminder email delivery is disabled")
    if is_delivery_disabled(db):
        raise HTTPException(
            status_code=503,
            detail="Reminder email delivery was disabled by an authorized operator",
        )
    if is_delivery_paused(db):
        raise HTTPException(status_code=503, detail="Reminder email delivery is paused")
    results = run_reminders(
        db,
        questionnaire_db,
        hospital_id=hospital_id,
        force=True,
        include_aggregate=include_aggregate,
    )
    failed = sum(result.status == "failed" for result in results)
    response = {
        "success": failed == 0,
        "processed": len(results),
        "sent": sum(result.status == "sent" for result in results),
        "failed": failed,
    }
    if failed:
        raise HTTPException(status_code=502, detail=response)
    return response


@router.post("/pause")
def pause_reports(
    db: Session = Depends(get_db),
    operator: dict = Depends(require_reminder_operator),
):
    configuration = set_delivery_paused(db, True, operator["email"])
    return {"paused": configuration.is_paused, "updatedBy": configuration.updated_by}


@router.post("/resume")
def resume_reports(
    db: Session = Depends(get_db),
    operator: dict = Depends(require_reminder_operator),
):
    configuration = set_delivery_paused(db, False, operator["email"])
    return {"paused": configuration.is_paused, "updatedBy": configuration.updated_by}


@router.post("/disable")
def disable_reports(
    db: Session = Depends(get_db),
    operator: dict = Depends(require_reminder_operator),
):
    configuration = set_delivery_disabled(db, True, operator["email"])
    return {"disabled": configuration.is_disabled, "updatedBy": configuration.updated_by}


@router.post("/enable")
def enable_reports(
    db: Session = Depends(get_db),
    operator: dict = Depends(require_reminder_operator),
):
    configuration = set_delivery_disabled(db, False, operator["email"])
    return {"disabled": configuration.is_disabled, "updatedBy": configuration.updated_by}
