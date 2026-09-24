"""Explicit pilot route: no production recipient lookup, logs, retries or CC."""
from dataclasses import dataclass

from ..core.email import send_email
from ..models.models import Hospital
from .reminder_dashboard import hospital_document
from .reminder_delivery import SENDER, SUPPORT, failure_alert_document
from .reminder_reports import build_report

PILOT_HOSPITAL_ID = 'clinic_00004'
PILOT_RECIPIENT = 'palivela.sanjana@tanuh.ai'


@dataclass(frozen=True)
class PilotEmail:
    kind: str
    subject: str
    html: str


def prepare_pilot(db, questionnaire_db, report_date, include_failure=False):
    hospital = db.query(Hospital).filter(Hospital.id == PILOT_HOSPITAL_ID).one_or_none()
    if hospital is None:
        raise ValueError('Pilot hospital clinic_00004 was not found in the application database')
    if hospital.name.strip().lower() in {'test', 'tanuh foundation'}:
        raise ValueError('Excluded hospitals cannot be used for this pilot')
    report = build_report(db, questionnaire_db, hospital, report_date)
    if report.collection_start_date is None or report.data_points < 1:
        raise ValueError('Pilot hospital has no completed submissions; no email will be sent')
    messages = [PilotEmail('hospital', f'[PILOT] PinkShieldAI | Thank you for your contribution - {hospital.name}',
                           hospital_document(report))]
    if include_failure:
        messages.append(PilotEmail('failure-simulation', '[PILOT SIMULATION] PinkShieldAI | Reminder delivery failure',
                                  failure_alert_document('hospital:' + PILOT_HOSPITAL_ID, PILOT_RECIPIENT,
                                                         report_date, 'PILOT — no production delivery', simulation=True)))
    return report, messages


def send_pilot_email(message):
    # Fixed envelope prevents overrides, template CC rows, or the production
    # failure-alert address from leaking into a pilot delivery.
    if not send_email(PILOT_RECIPIENT, message.subject, message.html, cc=None,
                      reply_to=SUPPORT, from_email=SENDER, raise_on_error=True):
        raise RuntimeError('SMTP did not confirm pilot acceptance')
