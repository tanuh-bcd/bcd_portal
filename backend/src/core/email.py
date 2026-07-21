import re
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from sqlalchemy.orm import Session
from .config import settings

logger = logging.getLogger(__name__)

LOGIN_URL = "https://bc-portal-dev.tanuh.ai/login"


def send_email(
    to_email: str,
    subject: str,
    html: str,
    cc: List[str] = None,
    reply_to: str = None,
    raise_on_error: bool = False,
) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email to %s", to_email)
        if raise_on_error:
            raise RuntimeError("SMTP is not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.attach(MIMEText(html, "html"))

    recipients = [to_email] + (cc or [])

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], recipients, msg.as_string())
        logger.info("Email sent to %s (cc: %s, subject: %s)", to_email, cc or "none", subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        if raise_on_error:
            raise
        return False


def _render(template_str: str, variables: dict) -> str:
    def replacer(match):
        key = match.group(1)
        return str(variables.get(key, match.group(0)))
    return re.sub(r"\{\{(\w+)\}\}", replacer, template_str)


def send_template_email(
    db: Session,
    template_key: str,
    to_email: str,
    variables: dict,
    reply_to: str = None,
    raise_on_error: bool = False,
) -> bool:
    from ..models.models import EmailTemplate, EmailTemplateCc

    template = db.query(EmailTemplate).filter(EmailTemplate.template_key == template_key).first()
    if not template:
        logger.warning("Email template '%s' not found in DB — skipping email to %s", template_key, to_email)
        if raise_on_error:
            raise RuntimeError(f"Email template '{template_key}' was not found")
        return False

    cc_rows = db.query(EmailTemplateCc).filter(EmailTemplateCc.template_key == template_key).all()
    cc_list = [row.cc_email for row in cc_rows if row.cc_email != to_email]

    variables.setdefault("login_url", LOGIN_URL)

    subject = _render(template.subject, variables)
    html = _render(template.body_html, variables)
    return send_email(
        to_email,
        subject,
        html,
        cc=cc_list if cc_list else None,
        reply_to=reply_to,
        raise_on_error=raise_on_error,
    )
