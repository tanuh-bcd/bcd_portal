# PinkShield AI Reminder Email Operations

## Overview

The reminder job sends hospital-level aggregate progress emails at most once every 14 days. It counts distinct patient sessions created in the current calendar quarter as data points, counts distinct assessed sessions in that quarter as assessments, and calculates pending submissions against a configurable target that defaults to 200.

Data-point totals are read from the questionnaire database using the same completed-session and hospital mapping used by the clinician dashboard. Assessment and attachment quality figures are then read from the main application database.

The email also reports aggregate data-quality indicators: submissions with explicitly blank stored questionnaire answers, assessments missing core mammography fields, missing standard CC/MLO left/right views, missing mammogram reports, and assessments where the routine-view flag is not confirmed. The current schema cannot detect omitted conditional questionnaire questions or evaluate positioning, exposure, compression, artefacts, or diagnostic image quality from mammogram pixels.

The job is separate from the web request process. An email or scheduler failure therefore does not interrupt the website or patient submissions.

## GCP and sender configuration

Production secrets are resolved through Google Secret Manager in project `bcd-prototypes`. The repository uses secret names prefixed with `bcd-`. Configure the following values without committing them to Git:

- `SMTP_HOST` (normally `smtp.gmail.com`)
- `SMTP_PORT` (normally `587`)
- `SMTP_USER` (the approved PinkShield AI sender account)
- `SMTP_PASSWORD` (a Google App Password or Workspace SMTP relay credential)
- `SMTP_FROM` (for example, `PinkShield AI <approved-account@tanuh.ai>`)
- `REMINDER_EMAIL_ENABLED` (`false` during validation; `true` after approval)
- `REMINDER_RECIPIENT_EMAIL` (optional safety override for an approved test recipient)
- `REMINDER_QUARTERLY_TARGET` (defaults to `200`)
- `REMINDER_INTERVAL_DAYS` (defaults to `14`)
- `REMINDER_PORTAL_URL`
- `REMINDER_SUPPORT_EMAIL`
- `REMINDER_REPLY_TO`
- `REMINDER_TIMEZONE` (defaults to `Asia/Kolkata`)

The VM or backend container service account needs Secret Manager accessor permission for these secrets.

For local interval testing only, set `REMINDER_INTERVAL_DAYS=1`. Keep the production Secret Manager value at `14` until a deliberate production schedule change is approved.

The repository includes an ignored `.env.reminder.local` file configured for the approved test recipient `manisha.verma@tanuh.ai`, the sender identity `breastcancerscreening@tanuh.ai`, a one-day interval, and live delivery disabled. Load it into the shell before a local dry run. It deliberately contains no SMTP password. Live delivery must remain disabled until an App Password or Workspace relay credential is supplied securely for an intentional pilot.

When `REMINDER_RECIPIENT_EMAIL` is empty in production, each report goes to its hospital's registered email. When it is set, every generated report goes to that override address, which prevents accidental hospital delivery during a pilot.

Do not use a normal Google account password for SMTP. Rotate any password that has been shared through chat, email, tickets, or logs.

## Database setup

Apply `database/migrations/20260721_add_reminder_email_reporting.sql` to the main application database before enabling delivery. It creates the audit table and installs the branded database email template.

The migration does not alter patient, assessment, hospital, or user records.

## Validation

Run a dry run first. A dry run calculates each hospital's figures and creates an audit record without contacting SMTP. It can be restricted to one pilot hospital and can use a specified reporting date for verification.

Compare the resulting counts with manually verified database totals. After approval, test actual delivery with a controlled pilot hospital or internal recipient before enabling all hospitals.

## Scheduling

Systemd service and timer definitions are provided under `deploy/systemd`. The timer checks daily at approximately 9:00 AM India Standard Time. The application sends only when a hospital has no successful email in the preceding 14 days.

Checking daily instead of using a day-of-month interval preserves a true 14-day rule across month and year boundaries. The timer is persistent, so a missed run is performed after the VM becomes available again.

Install and enable the timer on the production VM only after the database migration, secrets, recipient list, pilot delivery, and email wording have been approved.

## Safety and auditing

Each attempt records the hospital, recipient, reporting date, quarter, counts, target, status, error, and successful delivery time. A hospital cannot receive two successful reports for the same reporting date. Failed attempts can be retried, and successful deliveries determine when the next 14-day interval begins.

The email contains aggregate counts only. It does not include patient names, answers, identifiers, images, reports, or clinical details.

Set `REMINDER_EMAIL_ENABLED=false` to stop actual delivery while retaining dry-run capability.
