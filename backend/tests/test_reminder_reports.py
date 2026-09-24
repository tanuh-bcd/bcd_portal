from datetime import date, datetime, timedelta

from sqlalchemy import bindparam, text

from backend.src.models.models import (
    Attachment,
    DoctorAssessment,
    Hospital,
    PatientSession,
    ReminderEmailLog,
    User,
)
from backend.src.services import reminder_reports
from backend.src.services.reminder_reports import (
    build_report,
    is_due,
    quarter_bounds,
    report_variables,
    run_reminders,
    send_report,
)
from backend.tests.conftest import TestQSession, TestSession


def add_questionnaire_session(q_db, session_id, hospital_name, submitted_at, blank_answer=False):
    q_db.execute(text("""
        INSERT INTO session_table
            (session_id, session_start_time, session_end_time, snehita_lifetime_risk, risk_category)
        VALUES (:session_id, :submitted_at, :submitted_at, '0.5', 'Evident Risk')
    """), {"session_id": session_id, "submitted_at": submitted_at.isoformat()})
    q_db.execute(text("""
        INSERT INTO session_data_table
            (session_data_id, session_id, question, answer, created_at)
        VALUES (:row_id, :session_id, 'Q45', :hospital_name, :submitted_at)
    """), {
        "row_id": f"{session_id}-hospital",
        "session_id": session_id,
        "hospital_name": hospital_name,
        "submitted_at": submitted_at.isoformat(),
    })
    if blank_answer:
        q_db.execute(text("""
            INSERT INTO session_data_table
                (session_data_id, session_id, question, answer, created_at)
            VALUES (:row_id, :session_id, 'Q1', '', :submitted_at)
        """), {
            "row_id": f"{session_id}-blank",
            "session_id": session_id,
            "submitted_at": submitted_at.isoformat(),
        })
    q_db.commit()


def delete_questionnaire_sessions(q_db, session_ids):
    statement = text("DELETE FROM session_data_table WHERE session_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    q_db.execute(statement, {"ids": session_ids})
    statement = text("DELETE FROM session_table WHERE session_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    q_db.execute(statement, {"ids": session_ids})
    q_db.commit()


def test_quarter_bounds():
    assert quarter_bounds(date(2026, 7, 21)) == (date(2026, 7, 1), date(2026, 10, 1))
    assert quarter_bounds(date(2026, 12, 31)) == (date(2026, 10, 1), date(2027, 1, 1))


def test_build_report_counts_contributions_from_collection_start():
    db = TestSession()
    q_db = TestQSession()
    hospital = db.query(Hospital).filter(Hospital.id == "clinic_00001").one()
    doctor = db.query(User).filter(User.email == "doctor@test.com").one()
    session_ids = ["reminder-q3-a", "reminder-q3-b", "reminder-old"]
    try:
        db.add_all([
            PatientSession(id=session_ids[0], hospital_id=hospital.id, consent_timestamp=datetime(2026, 7, 2)),
            PatientSession(id=session_ids[1], hospital_id=hospital.id, consent_timestamp=datetime(2026, 8, 2)),
            PatientSession(id=session_ids[2], hospital_id=hospital.id, consent_timestamp=datetime(2026, 6, 30)),
        ])
        db.flush()
        add_questionnaire_session(q_db, session_ids[0], hospital.name, datetime(2026, 7, 2), blank_answer=True)
        add_questionnaire_session(q_db, session_ids[1], hospital.name, datetime(2026, 8, 2))
        add_questionnaire_session(q_db, session_ids[2], hospital.name, datetime(2026, 6, 30))
        db.add_all([
            DoctorAssessment(
                patient_session_id=session_ids[0], hospital_id=hospital.id,
                doctor_id=doctor.id, created_at=datetime(2026, 7, 3),
                mammo_birads="2", mammo_density="B", clinical_findings={"left": "clear"},
                routine_views_uploaded=False,
            ),
            DoctorAssessment(
                patient_session_id=session_ids[2], hospital_id=hospital.id,
                doctor_id=doctor.id, created_at=datetime(2026, 7, 3),
            ),
        ])
        db.commit()
        assessment = db.query(DoctorAssessment).filter(
            DoctorAssessment.patient_session_id == session_ids[0]
        ).one()
        db.add_all([
            Attachment(
                assessment_id=assessment.id, file_type=file_type,
                file_name=f"{file_type}.dcm", storage_url=f"gs://test/{file_type}.dcm",
            )
            for file_type in ("mammo_cc_left", "mammo_cc_right", "mammo_mlo_left")
        ])
        db.commit()

        report = build_report(db, q_db, hospital, date(2026, 8, 10))
        assert report.collection_start_date == date(2026, 6, 30)
        assert report.data_points == 3
        assert report.assessments_submitted == 2
        assert report.mammography_cases == 1
        assert report.pending_submissions == 0
        assert report.assessment_backlog == 1
    finally:
        delete_questionnaire_sessions(q_db, session_ids)
        q_db.close()
        assessment_ids = [row[0] for row in db.query(DoctorAssessment.id).filter(
            DoctorAssessment.patient_session_id.in_(session_ids)
        ).all()]
        if assessment_ids:
            db.query(Attachment).filter(Attachment.assessment_id.in_(assessment_ids)).delete(synchronize_session=False)
        db.query(DoctorAssessment).filter(DoctorAssessment.patient_session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(PatientSession).filter(PatientSession.id.in_(session_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_report_variables_are_positive_and_target_free():
    db = TestSession()
    q_db = TestQSession()
    hospital = db.query(Hospital).filter(Hospital.id == "clinic_00001").one()
    session_ids = [f"over-target-{index}" for index in range(3)]
    try:
        db.add_all([
            PatientSession(id=session_id, hospital_id=hospital.id, consent_timestamp=datetime(2026, 7, 2))
            for session_id in session_ids
        ])
        db.commit()
        for session_id in session_ids:
            add_questionnaire_session(q_db, session_id, hospital.name, datetime(2026, 7, 2))
        report = build_report(db, q_db, hospital, date(2026, 8, 10))
        variables = report_variables(report)
        assert variables["collection_start_date"] == "02 July 2026"
        assert variables["data_points"] == 3
        assert variables["assessments_pending"] == 3
        assert variables["mammogram_images_pending"] == 3
        assert variables["mammogram_reports_pending"] == 3
        assert "quarterly_target" not in variables
        assert "pending_submissions" not in variables
        assert "missing_questionnaire_sessions" not in variables
    finally:
        delete_questionnaire_sessions(q_db, session_ids)
        q_db.close()
        db.query(PatientSession).filter(PatientSession.id.in_(session_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_configured_recipient_overrides_hospital_email(monkeypatch):
    db = TestSession()
    q_db = TestQSession()
    hospital = db.query(Hospital).filter(Hospital.id == "clinic_00001").one()
    monkeypatch.setattr(reminder_reports.settings, "REMINDER_RECIPIENT_EMAIL", "pilot@tanuh.ai")
    try:
        report = build_report(db, q_db, hospital, date(2026, 8, 10))
        assert report.recipient_email == "pilot@tanuh.ai"
    finally:
        q_db.close()
        db.close()


def test_hospitals_without_completed_collection_are_skipped():
    db = TestSession()
    q_db = TestQSession()
    try:
        assert run_reminders(
            db,
            q_db,
            report_date=date(2026, 8, 10),
            hospital_id="clinic_00001",
            dry_run=True,
            force=True,
        ) == []
    finally:
        q_db.close()
        db.close()


def test_due_check_uses_last_successful_delivery():
    db = TestSession()
    report_date = date(2026, 8, 20)
    try:
        db.query(ReminderEmailLog).filter(ReminderEmailLog.hospital_id == "clinic_00001").delete()
        db.commit()
        assert is_due(db, "clinic_00001", report_date, 14) is True

        db.add(ReminderEmailLog(
            hospital_id="clinic_00001",
            recipient_email="test@hospital.com",
            report_date=date(2026, 8, 10),
            quarter_start=date(2026, 7, 1),
            quarter_end=date(2026, 10, 1),
            data_points=10,
            assessments_submitted=8,
            pending_submissions=190,
            quarterly_target=200,
            status="sent",
            sent_at=datetime.combine(report_date - timedelta(days=13), datetime.min.time()),
        ))
        db.commit()
        assert is_due(db, "clinic_00001", report_date, 14) is False

        log = db.query(ReminderEmailLog).filter(ReminderEmailLog.hospital_id == "clinic_00001").one()
        log.sent_at = datetime.combine(report_date - timedelta(days=14), datetime.min.time())
        db.commit()
        assert is_due(db, "clinic_00001", report_date, 14) is True
    finally:
        db.query(ReminderEmailLog).filter(ReminderEmailLog.hospital_id == "clinic_00001").delete()
        db.commit()
        db.close()


def test_send_report_records_success_and_prevents_duplicate(monkeypatch):
    db = TestSession()
    q_db = TestQSession()
    hospital = db.query(Hospital).filter(Hospital.id == "clinic_00001").one()
    report_date = date(2026, 9, 1)
    session_id = "reminder-send-report"
    calls = []

    def fake_send(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr(reminder_reports, "send_template_email", fake_send)
    try:
        add_questionnaire_session(q_db, session_id, hospital.name, datetime(2026, 8, 15))
        db.query(ReminderEmailLog).filter(
            ReminderEmailLog.hospital_id == hospital.id,
            ReminderEmailLog.report_date == report_date,
        ).delete()
        db.commit()

        report = build_report(db, q_db, hospital, report_date)
        first = send_report(db, report)
        second = send_report(db, report)

        assert first.status == "sent"
        assert first.sent_at is not None
        assert second.id == first.id
        assert len(calls) == 1
        variables = calls[0][0][3]
        assert variables["collection_start_date"] != "Not started"
        assert "pending_submissions" not in variables
        assert "quarterly_target" not in variables
    finally:
        delete_questionnaire_sessions(q_db, [session_id])
        db.query(ReminderEmailLog).filter(
            ReminderEmailLog.hospital_id == hospital.id,
            ReminderEmailLog.report_date == report_date,
        ).delete()
        db.commit()
        db.close()
        q_db.close()
