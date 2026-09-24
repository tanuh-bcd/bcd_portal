from dataclasses import replace
from datetime import date
from unittest.mock import Mock

import pytest

from backend.src.services import reminder_pilot as pilot
from backend.tests.test_reminder_delivery import report


def prepare(monkeypatch, *, include_failure=True, started=True):
    hospital = Mock()
    hospital.name = 'Real Hospital <A>'
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = hospital
    snapshot = replace(report('clinic_00004', hospital.name),
                       collection_start_date=date(2026, 7, 1) if started else None)
    monkeypatch.setattr(pilot, 'build_report', lambda *args: snapshot)
    result = pilot.prepare_pilot(db, Mock(), date(2026, 9, 24), include_failure)
    db.commit.assert_not_called()
    db.add.assert_not_called()
    return result


def test_both_pilot_messages_are_routed_only_to_sanjana(monkeypatch):
    _, messages = prepare(monkeypatch)
    calls = []
    monkeypatch.setattr(pilot, 'send_email', lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    for message in messages:
        pilot.send_pilot_email(message)
    assert len(calls) == 2
    for args, kwargs in calls:
        assert args[0] == 'palivela.sanjana@tanuh.ai'
        assert kwargs['cc'] is None
        assert kwargs['from_email'] == 'PinkShieldAI <breastcancerscreening@tanuh.ai>'
        assert kwargs['reply_to'] == 'breastcancerscreening@tanuh.ai'
    assert 'Dear Real Hospital &lt;A&gt; Team' in messages[0].html
    assert 'PILOT SIMULATION ONLY' in messages[1].html
    assert 'No delivery failure was triggered' in messages[1].html


def test_pilot_does_not_send_before_collection_started(monkeypatch):
    with pytest.raises(ValueError, match='no completed submissions'):
        prepare(monkeypatch, started=False)


def test_pilot_smtp_failure_does_not_route_a_production_alert(monkeypatch):
    _, messages = prepare(monkeypatch, include_failure=False)
    send = Mock(side_effect=RuntimeError('SMTP unavailable'))
    monkeypatch.setattr(pilot, 'send_email', send)
    with pytest.raises(RuntimeError, match='SMTP unavailable'):
        pilot.send_pilot_email(messages[0])
    assert send.call_count == 1
    assert send.call_args.args[0] == pilot.PILOT_RECIPIENT


def test_pilot_cli_defaults_to_preview_and_prevents_reusing_receipt(monkeypatch, tmp_path):
    import json
    from contextlib import nullcontext
    from backend.src.jobs import send_reminder_pilot as job
    snapshot, messages = prepare(monkeypatch)
    monkeypatch.setattr(job, 'SessionLocal', lambda: nullcontext(Mock()))
    monkeypatch.setattr(job, 'QuestionnaireSessionLocal', lambda: nullcontext(Mock()))
    monkeypatch.setattr(job, 'prepare_pilot', lambda *args: (snapshot, messages))
    send = Mock()
    monkeypatch.setattr(job, 'send_pilot_email', send)
    monkeypatch.setattr('sys.argv', ['pilot', '--output-dir', str(tmp_path), '--include-failure-preview'])
    job.main()
    send.assert_not_called()
    receipt = json.loads((tmp_path / 'pilot-receipt.json').read_text())
    assert receipt['status'] == 'preview'
    assert receipt['to'] == pilot.PILOT_RECIPIENT
    assert receipt['cc'] == []
    assert (tmp_path / 'hospital.html').exists()
    assert (tmp_path / 'failure-simulation.html').exists()
    with pytest.raises(SystemExit, match='already has a receipt'):
        job.main()
    send.assert_not_called()


def test_database_diagnostic_includes_code_but_not_credentials():
    from sqlalchemy.exc import OperationalError
    from backend.src.jobs.send_reminder_pilot import pilot_error_detail
    original = Exception(2003, 'secret password and database endpoint')
    exc = OperationalError('SELECT sensitive_data', {'password': 'hidden'}, original)
    detail = pilot_error_detail(exc)
    assert '2003' in detail
    assert 'USE_CLOUD_SQL_CONNECTOR=true' in detail
    assert 'secret' not in detail
    assert 'sensitive_data' not in detail
    assert 'hidden' not in detail


def test_missing_smtp_settings_are_reported_without_values(monkeypatch):
    from backend.src.core import email
    from backend.src.jobs.send_reminder_pilot import pilot_error_detail
    monkeypatch.setattr(email.settings, 'SMTP_HOST', 'smtp.gmail.com')
    monkeypatch.setattr(email.settings, 'SMTP_USER', 'private-account@example.com')
    monkeypatch.setattr(email.settings, 'SMTP_PASSWORD', '')
    with pytest.raises(email.SMTPConfigurationError) as caught:
        email.validate_smtp_config()
    detail = pilot_error_detail(caught.value)
    assert 'SMTP_PASSWORD' in detail
    assert 'SMTP_USER' not in detail
    assert 'private-account' not in detail
