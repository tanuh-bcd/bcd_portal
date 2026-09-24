# PinkShieldAI fortnightly hospital contribution emails

**Deployment:** follow [the complete deployment checklist](reminder_deployment_checklist.md). The scheduler now honours the existing database pause/disable controls. The isolated pilot remains available via [the pilot guide](reminder_pilot.md).

The active scope is hospital reminders and their failure alerts only. All-hospitals reporting is deferred: the scheduler neither creates nor retries consolidated-summary deliveries.

Google Cloud Scheduler calls the OIDC-protected reminder endpoint daily at approximately 09:00 IST. Successful recipient deliveries become due again after 14 days. The job runs independently of normal website requests.

## Content and recipients

Hospital emails begin with a personalised, formal thank-you to the hospital team, followed by cumulative data from collection start through the reporting date: total completed subjects, reports uploaded, image records, image studies, and month-wise completed submissions. Cards use email-compatible HTML matching Stats.css (grey gradient cards, teal totals, rounded panels). A teal appreciation panel and pink PinkShieldAI wordmark introduce the letter; partner logos appear in the footer. A closing message encourages continued contributions and completion of pending records, followed by a portal button and team sign-off. Monthly charts are PNGs using the dashboard’s Poppins font and stacked risk colours; no age chart or patient-level data is included. Logos and charts are bundled as inline CID attachments, so external image hosting is unnecessary. Email clients may use the Arial fallback for card text where Poppins is unavailable.

Metric definitions:

- Subjects: distinct questionnaire sessions with a non-null `snehita_lifetime_risk`, mapped through the dashboard's institute question names to the hospital name.
- Reports uploaded: `mammo_reading` attachment records belonging to those subjects and that hospital.
- Image records: mammogram attachment records (`mammo_cc_left`, `mammo_cc_right`, `mammo_mlo_left`, `mammo_mlo_right`, or legacy `mammo_dicom`). This counts uploaded records, not frames within a DICOM file.
- Image studies: distinct subjects with one or more of those image records. The current schema has no study UID; this is not a count of distinct DICOM studies.
- Monthly distribution: completed subject submissions grouped by session end time, falling back to session start time. Zero months between collection start and report date are included. The stacks use the same risk thresholds as the website (0.4004, 0.574, 0.795), labels, and colours. Histories longer than 12 months wrap into additional panels rather than dropping older months.

The checked-in Analytics Dashboard has subject, risk, age, institute, and monthly charts; it does not currently contain image-record or image-study cards. The email adds the requested cards with the definitions above, using the existing attachment schema. Historical reports filter assessment/attachment creation dates but cannot reconstruct deleted files or earlier versions of edited records.

Every active hospital user with a nonempty external email receives their own hospital snapshot. Addresses are trimmed, lowercased, deduplicated per hospital, and excluded if they end in `@tanuh.ai` or match `psanjana2711@gmail.com`, `vermamanisha6200@gmail.com`, or `minminiselvam95@gmail.com`. Tanuh Foundation and the dashboard's Test institution are excluded. Hospitals without completed submissions receive no reminder. Once a hospital has its first completed submission and an eligible recipient, the first email is eligible on the next daily scheduler run. Later successful sends are separated by 14 days.

| Type | To | CC |
| --- | --- | --- |
| Hospital | Eligible active hospital users | bcs@tanuh.ai |
| Failure after three attempts | vaishnavi.joshi@tanuh.ai | None |

Both email types use `PinkShieldAI <breastcancerscreening@tanuh.ai>` as From and `breastcancerscreening@tanuh.ai` as Reply-To/support. These reminder-specific rules do not change other website emails. Legacy database template CC settings and `REMINDER_RECIPIENT_EMAIL` do not override these routes.


## Delivery and retries

Apply `database/migrations/20260921_add_reminder_deliveries.sql` before using the updated job. It creates `reminder_deliveries`; it preserves the original audit table. The old audit history is consulted for hospital cadence during migration.

A newly due cycle uses the current deployed `hospital_document()` template. There is no database email-template update needed for copy/layout edits. Existing failed cycles retry their original content and reporting-date snapshot; they are not silently replaced when the template changes. The next new cycle uses the revised template.

Each recipient/cycle has a stored HTML snapshot, status, attempt count, attempt date, error, and delivery/alert timestamp. A failed recipient is retried at most once per daily run date, for three attempts total. Successful recipients are not retried. After attempt three, one failure alert is sent; a failed alert remains pending for subsequent runs. After an exhausted cycle has been alerted and 14 days have elapsed from its start, a new cycle can begin. SMTP failures are isolated so processing continues for other recipients.

The CLI holds a MySQL advisory lock across a live run to prevent concurrent scheduler/manual executions. An SMTP acceptance followed by a process crash before the database commit can still cause a duplicate retry; SMTP offers no transactional exactly-once guarantee. A CC rejection alone does not resend a successfully accepted primary recipient.

## Preview and validation

Run from the backend directory (or inside the backend container):

```sh
python -m src.jobs.send_fortnightly_reminders --dry-run --force --preview-dir /tmp/reminder-previews
python -m src.jobs.send_fortnightly_reminders --dry-run --force --hospital-id HOSPITAL_ID --preview-dir /tmp/hospital-preview
```

Dry runs do not call SMTP or change delivery history. Preview files contain aggregate data; console output identifies intended recipients. Review figures and definitions against the website and review the recipient list before live delivery.

`--force` bypasses the interval check but does not resend an already-sent same-day cycle, reset failed attempts, or bypass the once-per-day retry rule. Use the current reporting date for live runs; `--report-date` is primarily for validation.

## Configuration and activation

Existing configuration resolves environment variables before Google Secret Manager. Configure approved SMTP credentials securely; the SMTP account must be allowed to send as breastcancerscreening@tanuh.ai. No credentials belong in Git.

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- `REMINDER_EMAIL_ENABLED`: must be true for live CLI sends; false disables live delivery.
- `REMINDER_INTERVAL_DAYS`: production value 14.
- `REMINDER_TIMEZONE`: Asia/Kolkata.
- `REMINDER_PORTAL_URL`: dashboard link for the deployed website.

Templates for these emails are rendered in `backend/src/services/reminder_dashboard.py`; delivery rules remain in `reminder_delivery.py`. Partner logos and the Poppins font/license are packaged in `backend/src/assets/reminders` and included by the existing Dockerfile. The original quarterly template and target settings are no longer used by the scheduled dashboard job.

Deploy the code and migration together, inspect dry-run previews, then configure the OIDC Cloud Scheduler job. Do not also enable the legacy systemd timer. Applying the migration, changing production configuration, and sending live emails are separate from local implementation and tests.


## Production activation sequence

These are deployment instructions, not commands executed by the implementation work.

1. Apply `database/migrations/20260921_add_reminder_deliveries.sql` to the application database if it has not already been applied. Preserve existing delivery records.
2. Configure `REMINDER_INTERVAL_DAYS=14`, `REMINDER_TIMEZONE=Asia/Kolkata`, and the deployed `REMINDER_PORTAL_URL`. Keep `REMINDER_EMAIL_ENABLED=false` during preview. Ensure the existing SMTP credentials are authorised for the configured sender.
3. From the repository root on the deployment host, build and restart the backend with `docker compose up -d --build backend`. This includes the new template, chart renderer, logos, and fonts.
4. Generate current-data previews without sending:

   ```sh
   docker exec bcd-backend python -m src.jobs.send_fortnightly_reminders --dry-run --force --preview-dir /tmp/reminder-previews
   docker cp bcd-backend:/tmp/reminder-previews ./reminder-previews
   ```

   Review the intended recipients printed by the job and the HTML previews. The all-hospitals summary is excluded even when no hospital filter is supplied.

5. When ready for activation, set `REMINDER_EMAIL_ENABLED=true` in the deployed configuration. Recreate the backend container if environment configuration changed, or restart it after a Secret Manager change, so it reads the new value.
6. Configure one paused Google Cloud Scheduler job to `POST /api/v1/reminders/run`, using the configured OIDC service account and exact audience. Follow `docs/reminder_deployment_checklist.md`, then release the database pause and resume the Scheduler job only when live delivery is intended.

7. Monitor `journalctl -u pinkshield-reminders.service` and `reminder_deliveries` after the first run. Expect hospital-recipient records only. Three failed SMTP attempts trigger the alert to vaishnavi.joshi@tanuh.ai, with no CC; if the SMTP service is still unavailable, the alert remains pending until it can be sent.

To pause live delivery, set `reminder_configuration.is_paused=1` or pause the Cloud Scheduler job. Set `REMINDER_EMAIL_ENABLED=false` and reload the backend to disable manual live invocations as well.
