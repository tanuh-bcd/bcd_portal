# Hospital reminder deployment checklist

This is the complete rollout checklist after the two pilot emails have been accepted. Production uses Google Cloud Scheduler with OIDC to call `POST /api/v1/reminders/run`. Do not also enable the legacy systemd timer. Run SQL in the **application database**, not the questionnaire database.

The scheduler endpoint validates both the token audience and the exact service-account email. A shared secret is intentionally unnecessary.

## Confirmed from the supplied schema exports

`1nd.csv` lists `reminder_configuration` and `reminder_email_log`; `reminder_deliveries` is absent. `2nd.csv` confirms the pause/disable columns. `3nd.csv` confirms that the original delivery history contains `hospital_id`, `status`, and `sent_at`, which the new job reads to preserve the existing interval. It does not insert into the old history table.

The updated scheduler honours the existing `reminder_configuration` flags: any row with `is_paused=1` or `is_disabled=1` prevents live hospital sends and retries. Dry-run previews remain available while paused. The separate manually invoked pilot remains independent.

## 1. Keep sending stopped

If the legacy timer is installed:

```sh
sudo systemctl stop pinkshield-reminders.timer
sudo systemctl disable pinkshield-reminders.timer
systemctl list-timers --all
crontab -l
```

Check for other reminder schedules (including root cron, older services, or a cloud scheduler). Disable the old reminder trigger before enabling the new one; do not disable unrelated jobs. Wait for any already-running reminder job to finish.

In the application database:

```sql
SELECT DATABASE();
SELECT id, is_paused, is_disabled FROM reminder_configuration;
UPDATE reminder_configuration SET is_paused = 1;
```

The database name should be the intended production application database. The pilot used `bcd_application2` on the Mac; do not assume that is your production connection merely because the name matches. If the configuration table has no rows, insert a paused row:

```sql
INSERT INTO reminder_configuration (id, is_paused, is_disabled)
VALUES (1, 1, 0);
```

Only run that INSERT if the table is empty. Take your normal database backup/snapshot before schema changes.

## 2. Apply only the new delivery-table migration

Open and execute the entire file:

`database/migrations/20260921_add_reminder_deliveries.sql`

It creates `reminder_deliveries` without replacing existing tables or deleting history. Do not rerun old template/history migrations. The appreciation and failure templates are now rendered from Python code, not the old `email_templates` records.

Verify:

```sql
SHOW CREATE TABLE reminder_deliveries;
SELECT COUNT(*) AS delivery_rows FROM reminder_deliveries;
```

A newly created table should have zero rows. Do not clear it if rows already exist.

## 3. Set persistent deployment configuration

Use the deployed `.env` (loaded by Docker Compose) or the intended Secret Manager entries. Terminal `export` values used for the successful pilot are not automatically copied into a Docker container and will not configure the backend or Cloud Scheduler job.

```dotenv
REMINDER_EMAIL_ENABLED=false
REMINDER_INTERVAL_DAYS=14
REMINDER_TIMEZONE=Asia/Kolkata
REMINDER_PORTAL_URL=https://YOUR-ACTUAL-PORTAL/login
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=breastcancerscreening@tanuh.ai
REMINDER_FROM_EMAIL=PinkShieldAI <breastcancerscreening@tanuh.ai>
CRON_SERVICE_ACCOUNT_EMAIL=YOUR-SCHEDULER-SERVICE-ACCOUNT
CRON_OIDC_AUDIENCE=https://YOUR-ACTUAL-BACKEND/api/v1/reminders/run
```

These setting names resolve to Secret Manager names with the `bcd-` prefix. Securely set `SMTP_PASSWORD` to the authorised SMTP account's app password. Do not commit secrets. If the From address is an alias, use the authorised authenticating account as SMTP_USER.

Remove `bcd-REMINDER_RECIPIENT_EMAIL` for production (or store an empty value). Do not set it to the literal strings `false`, `disabled`, or an old pilot address. Keep `bcd-REMINDER_TEMPLATE_TEST_ENABLED` false or absent.

Set MYSQL connection values to the intended production application and questionnaire databases. Do not blindly enable Cloud SQL: `USE_CLOUD_SQL_CONNECTOR=false` selects MYSQL_HOST/MYSQL_PORT; true selects CLOUD_SQL_CONNECTION_NAME instead. Both require database credentials valid for that target.

**Docker networking:** `127.0.0.1:3307` inside `bcd-backend` is the container itself, not the host or Mac. The pilot's host SSH tunnel is therefore not proof that Docker can reach the database. Configure the container-reachable production endpoint before proceeding. An unattended production service should not depend on a temporary laptop SSH session. Never substitute a guessed database host or Cloud SQL instance.

## 4. Deploy the code while paused

Deploy the updated working tree, including all new/untracked reminder files, not only modifications to existing files. Required additions include `reminder_delivery.py`, `reminder_dashboard.py`, `backend/src/assets/reminders/` (including both fonts), and the SQL migration. The new `reminder_pilot.py` and pilot job are useful for future isolated checks.

```sh
docker compose up -d --build backend
docker logs --tail 100 bcd-backend
```

The existing Dockerfile copies `backend/src`, including email assets. Keep the Cloud Scheduler job paused.

## 5. Preview against production data

```sh
docker exec -e REMINDER_EMAIL_ENABLED=false bcd-backend \
  python -m src.jobs.send_fortnightly_reminders \
  --dry-run --force --preview-dir /tmp/reminder-deployment-preview

docker cp bcd-backend:/tmp/reminder-deployment-preview ./reminder-deployment-preview
```

Open the HTML files in a browser. The printed recipients and report counts must match the intended production hospitals. Dry run writes preview files only, not delivery history or emails.

Check:

- Correct hospital name, cumulative totals and month-wise graph.
- Every active eligible hospital user is included separately, with duplicate addresses removed per hospital.
- Excluded users: all `@tanuh.ai`, `psanjana2711@gmail.com`, `vermamanisha6200@gmail.com`, `minminiselvam95@gmail.com`.
- Excluded hospitals: Test, Tanuh Foundation, and hospitals without completed submissions.
- All-hospitals summary is absent.
- The portal link points to the intended deployed website.

If the command reports connection/authentication/schema errors, resolve them before activation. The production SMTP settings must be persistently available as well; a successful local pilot verifies only the local settings.

## 6. Verify OIDC and enable configuration

Confirm the deployed endpoint rejects an unauthenticated request:

```sh
curl -i -X POST https://YOUR-ACTUAL-BACKEND/api/v1/reminders/run
```

Expected before enabling delivery: HTTP 401 without a token. HTTP 404 means the updated backend is not deployed. HTTP 503 mentioning scheduler authentication means the OIDC secrets are unavailable to the backend runtime.

Change persistent `REMINDER_EMAIL_ENABLED` to `true` and reload the container:

```sh
docker compose up -d --force-recreate backend
```

The database pause flag still prevents live sending at this stage.

## 7. Configure Cloud Scheduler, still paused

Create or update one daily HTTP job:

```sh
gcloud scheduler jobs create http pinkshield-hospital-reminders \
  --location=YOUR-SCHEDULER-REGION \
  --schedule="0 9 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://YOUR-ACTUAL-BACKEND/api/v1/reminders/run" \
  --http-method=POST \
  --oidc-service-account-email="YOUR-SCHEDULER-SERVICE-ACCOUNT" \
  --oidc-token-audience="https://YOUR-ACTUAL-BACKEND/api/v1/reminders/run" \
  --paused
```

If the job already exists, use `gcloud scheduler jobs update http` with the same URI, method, schedule, timezone, service account, audience, location, and `--paused`. The URI, configured audience secret, and scheduler token audience must match exactly. Grant only the invocation permissions required by your hosting platform; the application also checks the identity.

## 8. Activate live delivery

Only after the preceding checks, release the global pause/disable flags in the application database:

```sql
UPDATE reminder_configuration SET is_paused = 0, is_disabled = 0;
SELECT id, is_paused, is_disabled FROM reminder_configuration;
```

Unpause the Cloud Scheduler job:

```sh
gcloud scheduler jobs resume pinkshield-hospital-reminders \
  --location=YOUR-SCHEDULER-REGION
```

**This activates real hospital email delivery.** Cloud Scheduler calls the endpoint daily at 09:00 IST. The application sends only due recipients.

If you intentionally want a live check immediately, use `gcloud scheduler jobs run`; otherwise wait for the scheduled time. Never use `--force` for normal production sending.

## 9. Verify the first run

Check the Cloud Scheduler execution status and backend application logs for `POST /api/v1/reminders/run`. A successful HTTP response reports only the number of recipient deliveries processed; it does not expose addresses.

```sql
SELECT scope, recipient_email, cycle_date, status, attempts,
       last_attempt_date, sent_at, error_message, alert_sent_at
FROM reminder_deliveries
ORDER BY id DESC
LIMIT 100;
```

Expected behaviour:

- Hospital email From: `PinkShieldAI <breastcancerscreening@tanuh.ai>`; Reply-To: `breastcancerscreening@tanuh.ai`.
- Each eligible user receives only their hospital's statistics; CC `bcs@tanuh.ai` on each individual email.
- No all-hospitals email is scheduled.
- Each successfully delivered recipient becomes eligible again after 14 days.
- Failed recipients retry at most once per date, for three attempts total. Successful recipients are not resent with those retries.
- After three failed attempts, an alert goes only to `vaishnavi.joshi@tanuh.ai`, without CC. If SMTP is unavailable, alert delivery remains pending until it recovers.
- New cycles use current data and the deployed template. Retries use the original snapshot.
- SMTP acceptance is not proof of inbox placement; monitor bcs@tanuh.ai and failure alerts.

Legacy sent history can legitimately defer a hospital for the remainder of its previous 14-day interval. Zero processed records can also mean no eligible recipients, no started hospitals, or a paused/disabled job; check logs before using any override.

## Stop or pause

```sql
UPDATE reminder_configuration SET is_paused = 1;
```

```sh
gcloud scheduler jobs pause pinkshield-hospital-reminders \
  --location=YOUR-SCHEDULER-REGION
```

Pause is checked at the beginning of each job; it does not cancel an already-running SMTP send. To block future manual live invocations too, retain the database pause or set persistent `REMINDER_EMAIL_ENABLED=false` and reload the backend. Do not delete delivery history to pause or retry.
