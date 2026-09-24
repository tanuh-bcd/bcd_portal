import argparse
import logging
from pathlib import Path
from datetime import date

from sqlalchemy import text

from ..core.config import settings
from ..db.session import QuestionnaireSessionLocal, SessionLocal
from ..services.reminder_reports import run_reminders


def parse_args():
    parser = argparse.ArgumentParser(description="Send PinkShield AI fortnightly hospital updates")
    parser.add_argument("--dry-run", action="store_true", help="Preview reports without sending email or changing delivery history")
    parser.add_argument("--force", action="store_true", help="Ignore the 14-day due check")
    parser.add_argument("--hospital-id", help="Restrict the run to one hospital")
    parser.add_argument("--report-date", type=date.fromisoformat, help="Override report date (YYYY-MM-DD)")
    parser.add_argument("--preview-dir", help="Write HTML previews (requires --dry-run)")
    args = parser.parse_args()
    if args.preview_dir and not args.dry_run:
        parser.error("--preview-dir requires --dry-run")
    return args


def main():
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    if not settings.REMINDER_EMAIL_ENABLED and not args.dry_run:
        raise SystemExit("Reminder emails are disabled. Set REMINDER_EMAIL_ENABLED=true after approval.")

    db = SessionLocal()
    questionnaire_db = QuestionnaireSessionLocal()
    lock_connection = None
    try:
        if not args.dry_run and db.bind.dialect.name == "mysql":
            lock_connection = db.bind.connect()
            if lock_connection.execute(text("SELECT GET_LOCK('pinkshield_reminders', 0)")).scalar() != 1:
                raise SystemExit("Another reminder job is running")
        results = run_reminders(
            db,
            questionnaire_db,
            report_date=args.report_date,
            hospital_id=args.hospital_id,
            dry_run=args.dry_run,
            force=args.force,
        )
        if args.preview_dir:
            Path(args.preview_dir).mkdir(parents=True, exist_ok=True)
        for index, result in enumerate(results):
            print(f"{result.scope}: {result.status}; to={result.recipient_email}; "
                  f"attempts={result.attempts}")
            if args.preview_dir:
                (Path(args.preview_dir) / f"reminder-{index + 1}.html").write_text(
                    result.body_html, encoding="utf-8")
        print(f"Processed {len(results)} recipient delivery record(s).")
    finally:
        if lock_connection is not None:
            try:
                lock_connection.execute(text("SELECT RELEASE_LOCK('pinkshield_reminders')"))
            finally:
                lock_connection.close()
        questionnaire_db.close()
        db.close()


if __name__ == "__main__":
    main()
