import re
import base64
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from typing import List
from sqlalchemy.orm import Session
from .config import settings

logger = logging.getLogger(__name__)

LOGIN_URL = "https://bc-portal-dev.tanuh.ai/login"


class SMTPConfigurationError(RuntimeError):
    """Missing configuration; message lists setting names, never credentials."""


def validate_smtp_config():
    missing = [name for name in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD')
               if not getattr(settings, name)]
    if missing:
        raise SMTPConfigurationError('Missing SMTP settings: ' + ', '.join(missing) +
                                     '. Supply them in the environment, .env, or accessible Secret Manager entries.')


def send_email(
    to_email: str,
    subject: str,
    html: str,
    cc: List[str] = None,
    reply_to: str = None,
    raise_on_error: bool = False,
    from_email: str = None,
) -> bool:
    try:
        validate_smtp_config()
    except SMTPConfigurationError:
        logger.warning("SMTP not configured — skipping email to %s", to_email)
        if raise_on_error:
            raise
        return False

    # Bundle generated dashboard charts/logos in the message itself. External
    # image loading and unsupported data: image URLs are unnecessary for readers.
    inline_images = []
    def embed_png(match):
        content_id = f"dashboard-{len(inline_images)}@pinkshield"
        part = MIMEImage(base64.b64decode(match.group(1), validate=True), _subtype="png")
        part.add_header("Content-ID", f"<{content_id}>")
        part.add_header("Content-Disposition", "inline", filename=f"dashboard-{len(inline_images)}.png")
        inline_images.append(part)
        return f'src="cid:{content_id}"'
    html = re.sub(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"', embed_png, html)
    msg = MIMEMultipart("related" if inline_images else "alternative")
    msg["Subject"] = subject
    msg["From"] = from_email or settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    if cc:
        msg["Cc"] = ", ".join(cc)
    if inline_images:
        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(html, "html", "utf-8"))
        msg.attach(alternative)
        for part in inline_images:
            msg.attach(part)
    else:
        msg.attach(MIMEText(html, "html", "utf-8"))

    recipients = [to_email] + (cc or [])

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            refused = server.sendmail(msg["From"], recipients, msg.as_string())
            if to_email in refused:
                raise smtplib.SMTPRecipientsRefused(refused)
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
