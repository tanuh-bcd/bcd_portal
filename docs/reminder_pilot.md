# clinic_00004 pilot: appreciation email and simulated failure alert

This pilot is separate from production scheduling. Both emails go **only** to `palivela.sanjana@tanuh.ai`, from `PinkShieldAI <breastcancerscreening@tanuh.ai>`, with no CC or BCC. Reply-To is `breastcancerscreening@tanuh.ai`. The internal-domain exclusion applies to production hospital users, not this explicitly authorised pilot recipient.

The appreciation email reads actual cumulative hospital statistics from the application and questionnaire databases. The second email is clearly labelled **PILOT SIMULATION**; it does not manufacture failed database records or trigger alerts to Vaishnavi. The pilot performs no database writes, does not use template CC rows, does not change production delivery history, and does not enable the timer. It refuses to send if clinic_00004 has not started completed data collection.

## What the supplied CSVs show

- `8st.csv`: older reminder delivery history, not source data for current analytics.
- `9st.csv`: a reminder control export with `is_paused=1` and `is_disabled=0`.
- `10st.csv`: stored templates, including hospital, aggregate and failure templates.
- `11st.csv`: template CC rows.
- `12st.csv`: user records. No user records or password hashes are copied into the pilot or edited.

These exports describe a different reminder schema from the new local delivery implementation. Do not activate production using the earlier rollout instructions until the existing paused-control mechanism and delivery schema have been reconciled. The pilot avoids both schemas by only reading hospital/questionnaire/assessment/attachment data.

## 1. Use the Mac database through its SSH tunnel

The user confirmed that the source database runs locally on their Mac. The working connection was verified on 24 September through `MYSQL_HOST=127.0.0.1` and `MYSQL_PORT=3307` on the machine running the pilot.

Keep the SSH tunnel open and use:

```sh
export USE_CLOUD_SQL_CONNECTOR=false
```

Do not enable Cloud SQL for this Mac database. `USE_CLOUD_SQL_CONNECTOR=true` ignores the direct host/port and connects to the configured Google Cloud SQL instance, where the Mac database credentials may be invalid. A previously exported shell value overrides `.env`, so explicitly set it to false even if `.env` already says false.

The pilot reads both the application database (`MYSQL_DB`) and questionnaire database (`MYSQL_DB_QUESTIONNAIRE`) through this tunnel. A real-data preview succeeded with 269 subjects, 234 reports, 944 image records and 236 image studies; these are snapshot counts, not fixed expected values.

## 2. Keep production disabled and configure SMTP

Keep the existing paused production system paused. Do not enable the timer or set `REMINDER_EMAIL_ENABLED=true` for this pilot. The dedicated `--send` flag authorises only its fixed pilot route.

The pilot uses the existing SMTP settings from the environment or Secret Manager: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD`. The SMTP account must be authorised to send as `breastcancerscreening@tanuh.ai`. Supply credentials securely, never in chat or checked-in files. Set `REMINDER_PORTAL_URL` to the deployed portal.

## 3. Generate both previews using real data

From the repository root:

```sh
USE_CLOUD_SQL_CONNECTOR=false .venv/bin/python -m backend.src.jobs.send_reminder_pilot \
  --include-failure-preview \
  --output-dir /tmp/clinic00004-pilot-preview-20260924
```

This does **not** send. It prints aggregate counts and writes:

- `hospital.html` — actual hospital appreciation email.
- `failure-simulation.html` — simulated failure alert.
- `pilot-receipt.json` — intended recipients, aggregate totals and preview status.

Open the HTML files in a browser. Verify hospital name, counts, chart, and cumulative period against the portal. A hospital without completed submissions is rejected rather than sent a zero-start reminder.

## 4. Send only the two pilot emails

Use a fresh output directory; the command refuses to reuse an existing receipt to prevent accidental repeat sends:

```sh
USE_CLOUD_SQL_CONNECTOR=false .venv/bin/python -m backend.src.jobs.send_reminder_pilot \
  --include-failure-preview \
  --send \
  --output-dir /tmp/clinic00004-pilot-send-20260924
```

This sends to `palivela.sanjana@tanuh.ai` only. Production hospital recipients, `bcs@tanuh.ai`, and `vaishnavi.joshi@tanuh.ai` are not included. There are no automatic retries or production failure alerts for the pilot.

Each email's local receipt is persisted before/after SMTP. `smtp_accepted` means the SMTP server accepted it, not proof of inbox delivery. If interrupted with a status of `sending`, check the inbox before attempting another run. If one email succeeds and the other fails, review the receipt and inbox before rerunning, since a new run would resend both.

## 5. Check the pilot mailbox

In `palivela.sanjana@tanuh.ai`, search for:

```text
from:breastcancerscreening@tanuh.ai subject:PILOT
```

Check Spam if necessary. Confirm that both messages have the correct From and To, no CC, readable cards and chart, a working portal link, and the correct Reply-To. The appreciation email must contain clinic_00004's actual hospital name and figures. The failure preview must say it is a simulation.

Production activation is a separate step after the pilot is accepted; it remains deferred.

## Production recipient exclusions

The hospital recipient selector includes only active hospital users, trims addresses, and deduplicates them case-insensitively. It excludes:

- All addresses ending in `@tanuh.ai`.
- `psanjana2711@gmail.com`.
- `vermamanisha6200@gmail.com`.
- `minminiselvam95@gmail.com`.

Hospital exclusions remain `Test` and `Tanuh Foundation`, case-insensitive. These are email-delivery filters, not account deletions or changes to `users.is_active`.

## Troubleshooting a stopped pilot

The CLI now records the failing stage and a sanitised database error code in `pilot-receipt.json` and prints actionable guidance.

- **2003 / application database connection:** the configured database endpoint is unavailable. Restore the SSH tunnel to the Mac and keep `USE_CLOUD_SQL_CONNECTOR=false`. Only use the connector when intentionally targeting a Cloud SQL database.
- **1045:** the instance was reached but MySQL rejected authentication. Correct `MYSQL_USER` / `MYSQL_PASSWORD` for that instance, or the intended IAM configuration. Google application login and MySQL login are separate. Nonempty `.env` values take precedence over Secret Manager, so an old local password can override a valid managed credential.
- **1044 / 1049:** check database permissions or database names.
- **1054 / 1146 during hospital statistics queries:** the connected schema lacks a required column/table. Reconcile the schema before sending; do not run unrelated migrations merely to suppress the error.

Use a new output directory for each retry, preserving previous receipts. Do not add `--send` until the real-data preview succeeds. The 24 September diagnostics found an unavailable local endpoint (2003) and rejected MySQL credentials when using the configured Cloud SQL connector (1045).

### Missing SMTP settings

`.env.reminder.local` is not automatically loaded by the pilot; its username alone does not configure SMTP. The default configuration loader reads `.env` plus exported environment values and accessible secrets.

For a Google Workspace/Gmail mailbox authorised to send as the pilot sender, configure the current shell (leave the Mac database tunnel open):

```sh
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=breastcancerscreening@tanuh.ai
read -rsp 'SMTP app password: ' SMTP_PASSWORD
export SMTP_PASSWORD
export USE_CLOUD_SQL_CONNECTOR=false
```

Use the account's approved app password, not the ordinary sign-in password. App passwords require 2-Step Verification and may be restricted by the organisation; consult the Workspace administrator if unavailable. If the From address is an alias, authenticate with an approved account authorised to send as that alias. Do not paste credentials into chat.

Then rerun the send command with a fresh output directory. Live pilots now validate SMTP configuration before querying the database and identify missing setting names without printing their values. The password above is only exported for the current shell; it is not written to project files.

Google documentation: https://support.google.com/accounts/answer/185833 and https://support.google.com/mail/answer/7104828
