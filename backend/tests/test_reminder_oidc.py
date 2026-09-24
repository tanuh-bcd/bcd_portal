from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.src.api import reminders


def test_oidc_rejects_missing_bearer_token(monkeypatch):
    monkeypatch.setattr(reminders.settings, "CRON_OIDC_AUDIENCE", "https://example.test/api/v1/reminders/run")
    monkeypatch.setattr(reminders.settings, "CRON_SERVICE_ACCOUNT_EMAIL", "scheduler@example.test")
    with pytest.raises(HTTPException) as caught:
        reminders.verify_scheduler_oidc("")
    assert caught.value.status_code == 401


def test_oidc_requires_exact_verified_scheduler_identity(monkeypatch):
    monkeypatch.setattr(reminders.settings, "CRON_OIDC_AUDIENCE", "https://example.test/api/v1/reminders/run")
    monkeypatch.setattr(reminders.settings, "CRON_SERVICE_ACCOUNT_EMAIL", "scheduler@example.test")
    monkeypatch.setattr(
        reminders.id_token,
        "verify_oauth2_token",
        lambda *args, **kwargs: {"email": "other@example.test", "email_verified": True},
    )
    with pytest.raises(HTTPException) as caught:
        reminders.verify_scheduler_oidc("Bearer valid-looking-token")
    assert caught.value.status_code == 403


def test_oidc_accepts_configured_scheduler_identity(monkeypatch):
    monkeypatch.setattr(reminders.settings, "CRON_OIDC_AUDIENCE", "https://example.test/api/v1/reminders/run")
    monkeypatch.setattr(reminders.settings, "CRON_SERVICE_ACCOUNT_EMAIL", "scheduler@example.test")
    monkeypatch.setattr(
        reminders.id_token,
        "verify_oauth2_token",
        lambda token, request, audience: {
            "email": "scheduler@example.test",
            "email_verified": True,
            "aud": audience,
        },
    )
    claims = reminders.verify_scheduler_oidc("Bearer token")
    assert claims["email"] == "scheduler@example.test"


def test_scheduler_run_honours_master_switch(monkeypatch):
    monkeypatch.setattr(reminders.settings, "REMINDER_EMAIL_ENABLED", False)
    with pytest.raises(HTTPException) as caught:
        reminders.run_due_hospital_reminders(SimpleNamespace())
    assert caught.value.status_code == 503


def test_scheduler_run_uses_job_and_returns_recipient_count(monkeypatch):
    class QuestionnaireSession:
        closed = False

        def close(self):
            self.closed = True

    questionnaire_db = QuestionnaireSession()
    db = SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    monkeypatch.setattr(reminders.settings, "REMINDER_EMAIL_ENABLED", True)
    monkeypatch.setattr(reminders, "QuestionnaireSessionLocal", lambda: questionnaire_db)
    monkeypatch.setattr(reminders, "run_reminders", lambda app_db, q_db: [1, 2, 3])
    response = reminders.run_due_hospital_reminders(db)
    assert response == {"status": "completed", "processed_recipient_deliveries": 3}
    assert questionnaire_db.closed is True
