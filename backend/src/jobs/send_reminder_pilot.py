"""Preview by default; --send explicitly sends only to the fixed pilot recipient."""
import argparse
import json
from pathlib import Path

from sqlalchemy import text

from ..db.session import SessionLocal, QuestionnaireSessionLocal
from ..core.email import SMTPConfigurationError, validate_smtp_config
from ..services.reminder_pilot import (PILOT_HOSPITAL_ID, PILOT_RECIPIENT, prepare_pilot,
                                      send_pilot_email)
from ..services.reminder_delivery import SENDER
from ..services.reminder_reports import current_date


def pilot_error_detail(exc):
    """Actionable diagnostics without raw SQL, parameters, or credentials."""
    if isinstance(exc, SMTPConfigurationError):
        return str(exc)
    original = getattr(exc, 'orig', exc)
    args = getattr(original, 'args', ())
    code = args[0] if args and isinstance(args[0], int) else None
    guidance = {
        2003: 'Cannot connect to MySQL. Start the configured database proxy, or use '
              'USE_CLOUD_SQL_CONNECTOR=true with valid Google application credentials.',
        2002: 'Cannot connect to the local MySQL socket. Check the database host and proxy.',
        1045: 'Database authentication was rejected. Check MYSQL_USER and the database password or IAM access.',
        1044: 'The database account does not have access to the configured database.',
        1049: 'The configured database does not exist. Check MYSQL_DB and MYSQL_DB_QUESTIONNAIRE.',
        1054: 'A required database column is missing. The database schema does not match this report code.',
        1146: 'A required database table is missing. Check the database names and schema.',
        2006: 'The database connection closed. Check database availability and retry the preview.',
        2013: 'The database connection was lost during the query. Check connectivity and retry the preview.',
    }
    if code is not None:
        return f'MySQL error {code}: ' + guidance.get(code, 'Check database access and schema; no SQL parameters are logged.')
    if type(original).__name__ in {'RefreshError', 'DefaultCredentialsError'}:
        return 'Google application credentials need attention. Run gcloud auth application-default login.'
    if isinstance(exc, ValueError):
        return str(exc)
    return 'Check the configuration for the stage reported below. No raw credentials or SQL parameters are logged.'


def main():
    parser = argparse.ArgumentParser(description='clinic_00004 pilot only; production scheduler remains unchanged')
    parser.add_argument('--output-dir', required=True, type=Path, help='New directory for previews and local receipt')
    parser.add_argument('--include-failure-preview', action='store_true', help='Also prepare a clearly labelled simulated alert')
    parser.add_argument('--send', action='store_true', help='Actually send to palivela.sanjana@tanuh.ai only, with no CC')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = args.output_dir / 'pilot-receipt.json'
    # Exclusive creation guards both repeated invocations and concurrent pilots.
    try:
        receipt_file = receipt_path.open('x', encoding='utf-8')
    except FileExistsError:
        raise SystemExit('This pilot directory already has a receipt. Review it before using a new output directory.')
    receipt = {'hospital_id': PILOT_HOSPITAL_ID, 'to': PILOT_RECIPIENT, 'cc': [], 'from': SENDER,
               'mode': 'send' if args.send else 'preview', 'status': 'preparing', 'stage': 'database setup', 'messages': []}
    def save():
        receipt_file.seek(0)
        json.dump(receipt, receipt_file, indent=2)
        receipt_file.truncate()
        receipt_file.flush()
    save()
    try:
        if args.send:
            receipt['stage'] = 'SMTP configuration'
            save()
            validate_smtp_config()
        with SessionLocal() as db, QuestionnaireSessionLocal() as qdb:
            receipt['stage'] = 'application database connection'
            save()
            db.execute(text('SELECT 1'))
            receipt['stage'] = 'questionnaire database connection'
            save()
            qdb.execute(text('SELECT 1'))
            receipt['stage'] = 'hospital statistics queries'
            save()
            report, messages = prepare_pilot(db, qdb, current_date(), args.include_failure_preview)
        receipt.update(hospital_name=report.hospital_name, report_date=report.report_date.isoformat(),
                       collection_start=report.collection_start_date.isoformat(),
                       totals={'subjects': report.data_points, 'reports_uploaded': report.reports_uploaded,
                               'image_records': report.image_records, 'image_studies': report.image_studies},
                       status='prepared')
        for message in messages:
            (args.output_dir / f'{message.kind}.html').write_text(message.html, encoding='utf-8')
            receipt['messages'].append({'kind': message.kind, 'subject': message.subject, 'status': 'preview'})
        save()
        print(f"Pilot: {PILOT_HOSPITAL_ID}; To: {PILOT_RECIPIENT}; CC: none", flush=True)
        print('Real-data totals:', receipt['totals'], flush=True)
        if args.send:
            for message, item in zip(messages, receipt['messages']):
                receipt['stage'] = 'SMTP send: ' + message.kind
                item['status'] = 'sending'
                save()
                send_pilot_email(message)
                item['status'] = 'smtp_accepted'
                save()
                print(f'{message.kind}: accepted by SMTP (inbox receipt must be checked)', flush=True)
        receipt['status'] = 'smtp_accepted' if args.send else 'preview'
        save()
    except Exception as exc:
        receipt['status'] = 'failed'
        receipt['error_type'] = type(exc).__name__
        receipt['error_detail'] = pilot_error_detail(exc)
        save()
        # Do not send a production failure alert, expose credentials, or retry.
        raise SystemExit(f"Pilot stopped during {receipt['stage']}: {type(exc).__name__}. "
                         f"{receipt['error_detail']} No automatic retry or production alert was sent.")
    finally:
        receipt_file.close()


if __name__ == '__main__':
    main()
