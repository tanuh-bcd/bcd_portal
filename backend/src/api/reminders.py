import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.session import QuestionnaireSessionLocal, get_db
from ..services.reminder_reports import run_reminders

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_scheduler_oidc(authorization: str = Header(default="")) -> dict:
    if not settings.CRON_OIDC_AUDIENCE or not settings.CRON_SERVICE_ACCOUNT_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reminder scheduler authentication is not configured",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
        )
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=settings.CRON_OIDC_AUDIENCE,
        )
    except Exception:
        logger.warning("Rejected invalid reminder scheduler OIDC token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid scheduler identity",
        )
    if not claims.get("email_verified") or claims.get("email", "").lower() != (
        settings.CRON_SERVICE_ACCOUNT_EMAIL.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scheduler identity is not authorised",
        )
    return claims


@router.post("/run", dependencies=[Depends(verify_scheduler_oidc)])
def run_due_hospital_reminders(db: Session = Depends(get_db)):
    if not settings.REMINDER_EMAIL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reminder delivery is disabled",
        )

    lock_acquired = True
    if db.bind.dialect.name == "mysql":
        lock_acquired = db.execute(
            text("SELECT GET_LOCK('pinkshield_reminders', 0)")
        ).scalar() == 1
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another reminder run is active",
        )

    questionnaire_db = QuestionnaireSessionLocal()
    try:
        results = run_reminders(db, questionnaire_db)
        return {
            "status": "completed",
            "processed_recipient_deliveries": len(results),
        }
    finally:
        questionnaire_db.close()
        if db.bind.dialect.name == "mysql":
            db.execute(text("SELECT RELEASE_LOCK('pinkshield_reminders')"))
