"""Dashboard email rendering and durable, recipient-specific delivery cycles."""
from datetime import datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from sqlalchemy import func, inspect, text
import logging

from ..core.config import settings
from ..core.email import send_email
from ..models.models import Hospital, ReminderDelivery, ReminderEmailLog, User
from .reminder_reports import build_report
from .reminder_dashboard import dashboard_fragment, email_document, hospital_document

SENDER = settings.REMINDER_FROM_EMAIL
SUPPORT = "breastcancerscreening@tanuh.ai"
OPERATIONS = "bcs@tanuh.ai"
FAILURE_RECIPIENT = "vaishnavi.joshi@tanuh.ai"
EXCLUDED_HOSPITAL_EMAILS = frozenset({
    "psanjana2711@gmail.com",
    "vermamanisha6200@gmail.com",
    "minminiselvam95@gmail.com",
})


def hospital_recipients(db, hospital_id):
    emails = db.query(User.email).filter(User.hospital_id == hospital_id,
                                        User.is_active.is_(True)).all()
    return sorted({email.strip().lower() for (email,) in emails
                   if email and '@' in email
                   and not email.strip().lower().endswith('@tanuh.ai')
                   and email.strip().lower() not in EXCLUDED_HOSPITAL_EMAILS})


def _now():
    return datetime.now(ZoneInfo(settings.REMINDER_TIMEZONE)).replace(tzinfo=None)


def failure_alert_document(scope, recipient, report_date, reference, simulation=False):
    notice = ('<p><strong>PILOT SIMULATION ONLY.</strong> No delivery failure was triggered. '
              'This is a preview of the alert sent after three failed attempts.</p>' if simulation else '')
    content = (notice + '<h2>Reminder delivery failed after three attempts</h2>'
               f'<p>Scope: {escape(scope)}</p>'
               f'<p>Recipient: {escape(recipient)}</p>'
               f'<p>Cycle: {report_date.isoformat()}</p>'
               f'<p>Delivery reference: {escape(str(reference))}. Review the delivery log for details.</p>')
    return email_document(content, heading="Delivery alert",
                          subtitle="Pilot simulation" if simulation else "Reminder delivery requires attention")


def deliver(db, delivery, today):
    """At most one attempt per day; alert once after three failed attempts."""
    if delivery.status == 'sent':
        return
    if delivery.attempts < 3 and delivery.last_attempt_date != today:
        delivery.attempts += 1
        delivery.last_attempt_date = today
        delivery.status = 'sending'
        db.commit()  # Persist before SMTP; a process crash must not reset the retry budget.
        try:
            sent = send_email(delivery.recipient_email, delivery.subject, delivery.body_html,
                              cc=[OPERATIONS] if delivery.scope.startswith('hospital:') else None,
                              reply_to=SUPPORT, from_email=SENDER, raise_on_error=True)
            if not sent:
                raise RuntimeError('SMTP did not confirm delivery')
            delivery.status = 'sent'
            delivery.sent_at = _now()
            delivery.error_message = None
        except Exception as exc:
            delivery.status = 'failed'
            delivery.error_message = str(exc)[:2000]
        db.commit()
    if delivery.attempts >= 3 and delivery.status != 'sent' and not delivery.alert_sent_at:
        delivery.status = 'failed'
        # Do not include raw SMTP errors: they may contain server or account details.
        content = failure_alert_document(delivery.scope, delivery.recipient_email,
                                         delivery.cycle_date, delivery.id)
        try:
            if send_email(FAILURE_RECIPIENT, 'PinkShieldAI | Reminder delivery failed',
                          content, cc=None, reply_to=SUPPORT,
                          from_email=SENDER, raise_on_error=True):
                delivery.alert_sent_at = _now()
        except Exception:
            # Leave alert pending for the next scheduler run; never reset report attempts.
            pass
        db.commit()


def schedule_delivery(db, scope, recipient, subject, body, today, dry_run=False, force=False):
    previous = db.query(ReminderDelivery).filter_by(scope=scope, recipient_email=recipient).order_by(
        ReminderDelivery.cycle_date.desc()).first()
    if previous and previous.status != 'sent' and previous.status != 'dry_run':
        if not dry_run:
            deliver(db, previous, today)
        if previous.attempts < 3 or today < previous.cycle_date + timedelta(days=settings.REMINDER_INTERVAL_DAYS):
            return previous
        if not previous.alert_sent_at:
            return previous
    if previous and previous.status == 'sent':
        if previous.cycle_date == today:
            return None
        if not force and previous.sent_at.date() > today - timedelta(days=settings.REMINDER_INTERVAL_DAYS):
            return None
    # Respect the legacy hospital cadence on the first run after migration.
    if not previous and scope.startswith('hospital:') and not force:
        last_sent = db.query(func.max(ReminderEmailLog.sent_at)).filter(
            ReminderEmailLog.hospital_id == scope.split(':', 1)[1],
            ReminderEmailLog.status == 'sent').scalar()
        if last_sent and last_sent.date() > today - timedelta(days=settings.REMINDER_INTERVAL_DAYS):
            return None
    if dry_run:
        return ReminderDelivery(scope=scope, recipient_email=recipient, cycle_date=today,
                                subject=subject, body_html=body, status='dry_run', attempts=0)
    delivery = ReminderDelivery(scope=scope, recipient_email=recipient, cycle_date=today,
                                subject=subject, body_html=body, status='pending', attempts=0)
    db.add(delivery)
    db.commit()
    deliver(db, delivery, today)
    return delivery


def run_dashboard_reminders(db, questionnaire_db, today, hospital_id=None, dry_run=False, force=False):
    if not dry_run and inspect(db.get_bind()).has_table('reminder_configuration'):
        controls = db.execute(text('SELECT is_paused, is_disabled FROM reminder_configuration')).all()
        if any(row.is_paused or row.is_disabled for row in controls):
            logging.getLogger(__name__).info('Reminder delivery is paused or disabled in reminder_configuration')
            return []
    hospitals = db.query(Hospital).filter(func.lower(func.trim(Hospital.name)).notin_(
        ['tanuh foundation', 'test']))
    if hospital_id:
        hospitals = hospitals.filter(Hospital.id == hospital_id)
    results = []
    for hospital in hospitals.order_by(Hospital.id).all():
        report = build_report(db, questionnaire_db, hospital, today)
        if report.collection_start_date is None:
            continue
        body = hospital_document(report)
        for recipient in hospital_recipients(db, hospital.id):
            result = schedule_delivery(db, 'hospital:' + hospital.id, recipient,
                                       f'PinkShieldAI | Thank you for your contribution - {hospital.name}',
                                       body, today, dry_run, force)
            if result:
                results.append(result)
    # All-hospitals reporting is deferred: do not create or retry its deliveries.
    return results
