"""Tests for the public questionnaire submission flow (/api/submit)."""
import pytest
from sqlalchemy import text

from backend.tests.conftest import TestQSession


@pytest.fixture
def q_session():
    """Create a questionnaire session for testing."""
    db = TestQSession()
    session_id = "test-public-session-001"
    db.execute(
        text("INSERT OR IGNORE INTO session_table (session_id, ip_address, session_start_time) VALUES (:sid, :ip, :ts)"),
        {"sid": session_id, "ip": "127.0.0.1", "ts": "2026-06-08 10:00:00"},
    )
    db.commit()
    yield session_id
    db.execute(text("DELETE FROM session_data_table WHERE session_id = :sid"), {"sid": session_id})
    db.execute(text("DELETE FROM session_table WHERE session_id = :sid"), {"sid": session_id})
    db.commit()
    db.close()


class TestPublicSubmit:
    """Tests for POST /api/submit."""

    def test_submit_all_string_values(self, client, q_session):
        res = client.post("/api/submit", json={
            "sessionId": q_session,
            "formDataEn": {"Q1": "42", "Q10": "13", "Q14": "Yes"}
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "riskPercentage" in data

    def test_submit_with_list_values(self, client, q_session):
        """Checkbox answers produce list values — must not cause 422."""
        res = client.post("/api/submit", json={
            "sessionId": q_session,
            "formDataEn": {
                "Q1": "45",
                "Q43": ["Breast Cancer", "Ovarian Cancer"],
                "Q10": "12",
            }
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True

        db = TestQSession()
        row = db.execute(
            text("SELECT answer FROM session_data_table WHERE session_id = :sid AND question = :q"),
            {"sid": q_session, "q": "Q43"},
        ).fetchone()
        db.close()
        assert row is not None
        assert "Breast Cancer" in row[0]
        assert "Ovarian Cancer" in row[0]

    def test_submit_with_numeric_values(self, client, q_session):
        """Number inputs may send int/float — must not cause 422."""
        res = client.post("/api/submit", json={
            "sessionId": q_session,
            "formDataEn": {"Q1": 42, "Q10": 13}
        })
        assert res.status_code == 200
        assert res.json()["success"] is True

    def test_submit_missing_session_id(self, client):
        res = client.post("/api/submit", json={
            "sessionId": "",
            "formDataEn": {"Q1": "42"}
        })
        assert res.status_code == 400

    def test_submit_missing_form_data(self, client, q_session):
        res = client.post("/api/submit", json={
            "sessionId": q_session,
            "formDataEn": {}
        })
        assert res.status_code == 400

    def test_risk_calculation_baseline(self, client, q_session):
        res = client.post("/api/submit", json={
            "sessionId": q_session,
            "formDataEn": {
                "Q1": "30", "Q10": "14", "Q12_Current": "Yes",
                "Q14": "Yes", "Q16": "Before 25", "Q17": "greater than 24 months",
                "Q21": "No", "Q40": "No",
            }
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert float(data["riskPercentage"]) > 0

    def test_session_end_time_set(self, client, q_session):
        client.post("/api/submit", json={
            "sessionId": q_session,
            "formDataEn": {"Q1": "42"}
        })
        db = TestQSession()
        row = db.execute(
            text("SELECT session_end_time, risk_category FROM session_table WHERE session_id = :sid"),
            {"sid": q_session},
        ).fetchone()
        db.close()
        assert row[0] is not None
        assert row[1] is not None

    def test_version_2_submission_uses_existing_model_without_biopsy(self, client):
        session_id = "test-public-session-v2"
        db = TestQSession()
        db.execute(
            text(
                "INSERT INTO session_table "
                "(session_id, ip_address, session_start_time, questionnaire_version) "
                "VALUES (:sid, :ip, :ts, 2)"
            ),
            {"sid": session_id, "ip": "127.0.0.1", "ts": "2026-09-08 10:00:00"},
        )
        db.commit()
        db.close()

        try:
            res = client.post("/api/submit", json={
                "sessionId": session_id,
                "formDataEn": {
                    "V2_Q03": "42",
                    "V2_Q11A": "13",
                    "V2_Q11_CYCLES": "No",
                    "V2_Q13": "Yes",
                    "V2_Q13_AGE_FIRST_BIRTH": "25 to 29",
                    "V2_Q13E": "Greater than 24 months",
                    "V2_Q17A": "First Order (Mother, Sibling, Father)",
                },
            })
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["questionnaireVersion"] == 2
            assert data["riskCalculated"] is True
            assert float(data["riskPercentage"]) > 0

            db = TestQSession()
            row = db.execute(
                text(
                    "SELECT session_end_time, snehita_lifetime_risk, risk_category "
                    "FROM session_table WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).fetchone()
            assert row[0] is not None
            assert row[1] is not None
            assert row[2] is not None
            db.close()
        finally:
            db = TestQSession()
            db.execute(text("DELETE FROM session_data_table WHERE session_id = :sid"), {"sid": session_id})
            db.execute(text("DELETE FROM session_table WHERE session_id = :sid"), {"sid": session_id})
            db.commit()
            db.close()


class TestSessionStart:
    """Tests for POST /api/session/start."""

    def test_start_session(self, client):
        res = client.post("/api/session/start")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "sessionId" in data
        assert len(data["sessionId"]) > 0

        db = TestQSession()
        db.execute(text("DELETE FROM session_table WHERE session_id = :sid"), {"sid": data["sessionId"]})
        db.commit()
        db.close()

    def test_start_session_with_requested_version(self, client):
        res = client.post("/api/session/start?version=2")
        assert res.status_code == 200
        data = res.json()
        assert data["questionnaireVersion"] == 2

        db = TestQSession()
        row = db.execute(
            text("SELECT questionnaire_version FROM session_table WHERE session_id = :sid"),
            {"sid": data["sessionId"]},
        ).fetchone()
        assert row[0] == 2
        db.execute(text("DELETE FROM session_table WHERE session_id = :sid"), {"sid": data["sessionId"]})
        db.commit()
        db.close()
