from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.src.models.models import Hospital, User, ReminderDelivery, ReminderEmailLog
from backend.src.services import reminder_delivery as service
from backend.src.services.reminder_reports import ReminderReport


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    for model in (Hospital, User, ReminderDelivery, ReminderEmailLog):
        model.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def report(hospital_id='a', name='Hospital A'):
    return ReminderReport(hospital_id, name, 'Team', 'unused@example.com', date(2026, 9, 21),
                          date(2026, 7, 1), date(2026, 7, 1), date(2026, 10, 1),
                          5, 2, 1, 0, 3, 0, 0, 0, 0, 0, 0,
                          reports_uploaded=2, image_records=4, image_studies=1,
                          month_counts={'2026-07': 2, '2026-09': 3})


def test_recipients_active_external_unique(db):
    for email, active in [(' Doctor@Hospital.org ', True), ('doctor@hospital.org', True),
                          ('person@TANUH.AI', True), (' PSANJANA2711@gmail.com ', True),
                          ('vermamanisha6200@gmail.com', True), ('minminiselvam95@gmail.com', True),
                          ('inactive@hospital.org', False)]:
        db.add(User(hospital_id='a', email=email, password_hash='unused', is_active=active))
    db.add(User(hospital_id='b', email='other@hospital.org', password_hash='unused', is_active=True))
    db.commit()
    assert service.hospital_recipients(db, 'a') == ['doctor@hospital.org']


def test_retry_third_failure_alert_once_and_new_cycle(db, monkeypatch):
    calls = []
    def send(to, *args, **kwargs):
        calls.append((to, kwargs))
        if to != service.FAILURE_RECIPIENT:
            raise RuntimeError('rejected')
        return True
    monkeypatch.setattr(service, 'send_email', send)
    today = date(2026, 9, 21)
    for offset in [0, 0, 1, 2, 2, 3]:
        service.schedule_delivery(db, 'hospital:a', 'doc@hospital.org', 'Subject', 'Body',
                                  today + timedelta(days=offset))
        if offset < 2:
            assert not any(to == service.FAILURE_RECIPIENT for to, _ in calls)
    delivery = db.query(ReminderDelivery).one()
    assert delivery.attempts == 3
    assert len(calls) == 4
    assert calls[-1][0] == service.FAILURE_RECIPIENT
    assert calls[-1][1]['cc'] is None
    assert all(kwargs['from_email'] == service.SENDER for _, kwargs in calls)
    assert calls[0][1]['cc'] == [service.OPERATIONS]
    service.schedule_delivery(db, 'hospital:a', 'doc@hospital.org', 'Subject', 'Body', today + timedelta(days=14))
    assert db.query(ReminderDelivery).count() == 2


def test_success_does_not_repeat_and_hospital_cc_is_preserved(db, monkeypatch):
    calls = []
    monkeypatch.setattr(service, 'send_email', lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    monkeypatch.setattr(service, '_now', lambda: datetime(2026, 9, 21, 9))
    today = date(2026, 9, 21)
    for offset in [0, 0, 1, 13]:
        service.schedule_delivery(db, 'hospital:a', 'doctor@hospital.org', 'Subject', 'Body',
                                  today + timedelta(days=offset))
    assert len(calls) == 1
    assert calls[0][1]['cc'] == [service.OPERATIONS]
    service.schedule_delivery(db, 'hospital:a', 'doctor@hospital.org', 'Subject', 'Body', today + timedelta(days=14))
    assert len(calls) == 2


def test_dry_run_no_send_no_database_write(db, monkeypatch):
    monkeypatch.setattr(service, 'send_email', lambda *a, **k: pytest.fail('Dry run sent email'))
    result = service.schedule_delivery(db, 'hospital:a', 'doc@hospital.org', 'Subject', 'Body',
                                       date(2026, 9, 21), dry_run=True)
    assert result.status == 'dry_run'
    assert db.query(ReminderDelivery).count() == 0


def test_hospital_isolation_exclusions_and_summary_is_deferred(db, monkeypatch):
    for key, name in [('a', 'Hospital A'), ('b', 'Hospital B'), ('c', 'Tanuh Foundation'), ('d', 'Test')]:
        db.add(Hospital(id=key, name=name, contact_person='Team', email=f'{key}@example.org'))
        db.add(User(hospital_id=key, email=f'user-{key}@example.org', password_hash='unused', is_active=True))
    db.commit()
    monkeypatch.setattr(service, 'build_report', lambda db, qdb, h, day: report(h.id, h.name))
    results = service.run_dashboard_reminders(db, None, date(2026, 9, 21), dry_run=True)
    assert len(results) == 2
    assert 'Hospital B' not in results[0].body_html
    assert 'Hospital A' not in results[1].body_html
    assert all(result.scope.startswith('hospital:') for result in results)
    assert all('Tanuh Foundation' not in result.body_html for result in results)
    assert len(service.run_dashboard_reminders(db, None, date(2026, 9, 21), hospital_id='a', dry_run=True)) == 1


def test_cards_months_and_html_escaping():
    html = service.dashboard_fragment(replace(report(), hospital_name='<Hospital>'))
    for label in ['Total subjects', 'Reports uploaded', 'Image records', 'Image studies', '2026-08']:
        assert label in html
    assert '&lt;Hospital&gt;' in html
    assert 'Age Distribution' not in html


def test_partial_recipient_failure_does_not_resend_success(db, monkeypatch):
    calls = []
    def send(to, *args, **kwargs):
        calls.append(to)
        if to == 'bad@hospital.org':
            raise RuntimeError('Rejected')
        return True
    monkeypatch.setattr(service, 'send_email', send)
    monkeypatch.setattr(service, '_now', lambda: datetime(2026, 9, 21, 9))
    for day in [date(2026, 9, 21), date(2026, 9, 22)]:
        for recipient in ['good@hospital.org', 'bad@hospital.org']:
            service.schedule_delivery(db, 'hospital:a', recipient, 'Subject', 'Body', day)
    assert calls.count('good@hospital.org') == 1
    assert calls.count('bad@hospital.org') == 2


def test_alert_failure_retries_alert_without_retrying_exhausted_report(db, monkeypatch):
    calls = []
    def send(to, *args, **kwargs):
        calls.append(to)
        raise RuntimeError('SMTP unavailable')
    monkeypatch.setattr(service, 'send_email', send)
    for offset in range(4):
        service.schedule_delivery(db, 'hospital:a', 'doc@hospital.org', 'Subject', 'Body',
                                  date(2026, 9, 21) + timedelta(days=offset))
    assert calls.count('doc@hospital.org') == 3
    assert calls.count(service.FAILURE_RECIPIENT) == 2
    assert db.query(ReminderDelivery).one().alert_sent_at is None


def test_uploaded_counts_and_months_are_cumulative_and_scoped():
    from backend.tests.conftest import TestSession, TestQSession
    from backend.tests.test_reminder_reports import add_questionnaire_session, delete_questionnaire_sessions
    from backend.src.models.models import PatientSession, DoctorAssessment, Attachment
    from backend.src.services.reminder_reports import build_report
    db, qdb = TestSession(), TestQSession()
    ids = ['metric-subject-old', 'metric-subject-new']
    try:
        hospital = db.query(Hospital).filter_by(id='clinic_00001').one()
        user = db.query(User).filter_by(email='doctor@test.com').one()
        for sid, dt in zip(ids, [datetime(2026, 1, 5), datetime(2026, 9, 5)]):
            db.add(PatientSession(id=sid, hospital_id=hospital.id, consent_timestamp=dt))
            add_questionnaire_session(qdb, sid, hospital.name, dt)
        db.flush()
        assessment = DoctorAssessment(patient_session_id=ids[0], hospital_id=hospital.id,
                                      doctor_id=user.id, created_at=datetime(2026, 1, 6))
        foreign = DoctorAssessment(patient_session_id=ids[1], hospital_id='clinic_00002',
                                   doctor_id=user.id, created_at=datetime(2026, 9, 6))
        db.add_all([assessment, foreign])
        db.flush()
        for owner, kind, dt in [(assessment, 'mammo_cc_left', datetime(2026, 1, 6)),
                                (assessment, 'mammo_cc_right', datetime(2026, 1, 6)),
                                (assessment, 'mammo_reading', datetime(2026, 1, 6)),
                                (assessment, 'mammo_mlo_left', datetime(2026, 10, 1)),
                                (foreign, 'mammo_cc_left', datetime(2026, 9, 6))]:
            db.add(Attachment(assessment_id=owner.id, file_type=kind, file_name='file',
                              storage_url='gs://test/file', created_at=dt))
        db.commit()
        result = build_report(db, qdb, hospital, date(2026, 9, 21))
        assert result.data_points == 2
        assert result.image_records == 2
        assert result.image_studies == 1
        assert result.reports_uploaded == 1
        assert result.month_counts == {'2026-01': 1, '2026-09': 1}
        assert result.month_risk_counts == {'2026-01': [0, 1, 0, 0], '2026-09': [0, 1, 0, 0]}
    finally:
        assessment_ids = [row[0] for row in db.query(DoctorAssessment.id).filter(
            DoctorAssessment.patient_session_id.in_(ids)).all()]
        db.query(Attachment).filter(Attachment.assessment_id.in_(assessment_ids)).delete(synchronize_session=False)
        db.query(DoctorAssessment).filter(DoctorAssessment.patient_session_id.in_(ids)).delete(synchronize_session=False)
        db.query(PatientSession).filter(PatientSession.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        delete_questionnaire_sessions(qdb, ids)
        db.close()
        qdb.close()


def test_dashboard_theme_and_chart_assets_are_embedded():
    import base64
    import re
    from io import BytesIO
    from PIL import Image
    from backend.src.services.reminder_dashboard import hospital_document
    sample = replace(report(), month_risk_counts={'2026-07': [1, 1, 0, 0], '2026-09': [1, 0, 1, 1]})
    html = hospital_document(sample)
    assert '#e91e8c' in html
    assert 'linear-gradient(135deg,#fdfbfb 0%,#ebedee 100%)' in html
    assert 'Your fortnightly contribution update' in html
    assert 'Dear Hospital A Team,' in html
    assert 'Thank you for your continued contribution' in html
    assert 'Continue contributing' in html
    assert 'Ministry of Education' in html
    assert 'Age Distribution' not in html
    images = re.findall(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"', html)
    assert len(images) == 4  # Three existing partner logos and one hospital chart.
    chart_data = re.search(r'<img src="data:image/png;base64,([A-Za-z0-9+/=]+)"[^>]*alt="Monthly subjects', html).group(1)
    chart = Image.open(BytesIO(base64.b64decode(chart_data))).convert('RGB')
    colors = set(chart.getdata())
    for color in [(110, 231, 183), (253, 224, 71), (251, 146, 60), (251, 113, 133)]:
        assert color in colors


def test_smtp_embeds_chart_and_preserves_routing(monkeypatch):
    from email import message_from_string
    from backend.src.core import email as email_module
    from backend.src.services.reminder_dashboard import email_document
    captured = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def starttls(self): pass
        def login(self, *args): pass
        def sendmail(self, sender, recipients, message):
            captured.append((sender, recipients, message))
            return {}
    monkeypatch.setattr(email_module.smtplib, 'SMTP', SMTP)
    monkeypatch.setattr(email_module.settings, 'SMTP_USER', 'test')
    monkeypatch.setattr(email_module.settings, 'SMTP_PASSWORD', 'test')
    assert email_module.send_email('doctor@hospital.org', 'Subject', email_document('<p>Test</p>'),
                                    cc=[service.OPERATIONS], from_email=service.SENDER,
                                    reply_to=service.SUPPORT, raise_on_error=True)
    sender, recipients, raw = captured[0]
    assert sender == service.SENDER
    assert recipients == ['doctor@hospital.org', service.OPERATIONS]
    message = message_from_string(raw)
    assert message['Reply-To'] == service.SUPPORT
    assert message.get_content_type() == 'multipart/related'
    parts = list(message.walk())
    images = [part for part in parts if part.get_content_type() == 'image/png']
    assert len(images) == 3
    html = next(part for part in parts if part.get_content_type() == 'text/html').get_payload(decode=True).decode()
    assert 'data:image' not in html
    for part in images:
        assert 'cid:' + part['Content-ID'].strip('<>') in html


def test_no_start_and_deferred_summary_never_send(db, monkeypatch):
    db.add(Hospital(id='new', name='New Hospital', contact_person='Team', email='office@new.org'))
    db.add(User(hospital_id='new', email='doctor@new.org', password_hash='unused', is_active=True))
    pending = ReminderDelivery(scope='all_hospitals', recipient_email=service.OPERATIONS,
                               cycle_date=date(2026, 9, 20), subject='Old summary', body_html='Old body',
                               attempts=1, status='failed', last_attempt_date=date(2026, 9, 20))
    db.add(pending)
    db.commit()
    monkeypatch.setattr(service, 'build_report', lambda *args: replace(report('new', 'New Hospital'),
                                                                      collection_start_date=None, data_points=0))
    monkeypatch.setattr(service, 'send_email', lambda *a, **k: pytest.fail('Unexpected email'))
    assert service.run_dashboard_reminders(db, None, date(2026, 9, 22)) == []
    assert db.query(ReminderDelivery).count() == 1
    assert pending.attempts == 1


def test_updated_template_applies_next_cycle_and_retry_keeps_snapshot(db, monkeypatch):
    sent_bodies = []
    def send(to, subject, body, **kwargs):
        sent_bodies.append(body)
        if len(sent_bodies) == 1:
            raise RuntimeError('Temporary failure')
        return True
    monkeypatch.setattr(service, 'send_email', send)
    monkeypatch.setattr(service, '_now', lambda: datetime(2026, 9, 22, 9))
    service.schedule_delivery(db, 'hospital:a', 'doctor@hospital.org', 'Old subject', 'Old body', date(2026, 9, 21))
    service.schedule_delivery(db, 'hospital:a', 'doctor@hospital.org', 'New subject', 'New body', date(2026, 9, 22))
    service.schedule_delivery(db, 'hospital:a', 'doctor@hospital.org', 'New subject', 'New body', date(2026, 10, 6))
    assert sent_bodies == ['Old body', 'Old body', 'New body']
    assert db.query(ReminderDelivery).count() == 2


@pytest.mark.parametrize('paused,disabled', [(1, 0), (0, 1), (1, 1)])
def test_existing_database_controls_stop_live_reminders(db, monkeypatch, paused, disabled):
    from sqlalchemy import text
    db.execute(text('CREATE TABLE reminder_configuration (id INTEGER PRIMARY KEY, is_paused INTEGER, is_disabled INTEGER)'))
    db.execute(text('INSERT INTO reminder_configuration VALUES (1, :paused, :disabled)'),
               {'paused': paused, 'disabled': disabled})
    db.commit()
    monkeypatch.setattr(service, 'send_email', lambda *a, **k: pytest.fail('Paused job sent email'))
    monkeypatch.setattr(service, 'build_report', lambda *a, **k: pytest.fail('Paused job queried reports'))
    assert service.run_dashboard_reminders(db, None, date(2026, 9, 24), force=True) == []


def test_database_pause_still_allows_dry_run(db, monkeypatch):
    from sqlalchemy import text
    db.execute(text('CREATE TABLE reminder_configuration (id INTEGER PRIMARY KEY, is_paused INTEGER, is_disabled INTEGER)'))
    db.execute(text('INSERT INTO reminder_configuration VALUES (1, 1, 0)'))
    db.add(Hospital(id='a', name='Hospital A', contact_person='Team', email='office@a.org'))
    db.add(User(hospital_id='a', email='doctor@a.org', password_hash='unused', is_active=True))
    db.commit()
    monkeypatch.setattr(service, 'build_report', lambda *a, **k: report())
    results = service.run_dashboard_reminders(db, None, date(2026, 9, 24), dry_run=True)
    assert len(results) == 1
    assert results[0].status == 'dry_run'
