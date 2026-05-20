import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.src.main import app
from backend.src.db.session import Base, get_db, get_questionnaire_db
from backend.src.core.security import get_password_hash, create_access_token

SQLALCHEMY_TEST_URL = "sqlite:///./test_bcd.db"
SQLALCHEMY_TEST_Q_URL = "sqlite:///./test_questionnaire.db"

engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
q_engine = create_engine(SQLALCHEMY_TEST_Q_URL, connect_args={"check_same_thread": False})

TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
TestQSession = sessionmaker(autocommit=False, autoflush=False, bind=q_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def override_get_questionnaire_db():
    db = TestQSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_databases():
    from backend.src.models.models import PatientResponse
    for col in PatientResponse.__table__.columns:
        if col.name == 'updated_at' and col.server_default is not None:
            col.server_default = None

    Base.metadata.create_all(bind=engine)

    from sqlalchemy import text
    conn = q_engine.connect()
    conn.execute(text("CREATE TABLE IF NOT EXISTS session_table (session_id TEXT PRIMARY KEY, ip_address TEXT, session_start_time TEXT, session_end_time TEXT, snehita_lifetime_risk TEXT)"))
    conn.execute(text("CREATE TABLE IF NOT EXISTS session_data_table (session_data_id TEXT PRIMARY KEY, session_id TEXT, question TEXT, answer TEXT, created_by TEXT, created_at TEXT)"))
    conn.commit()
    conn.close()

    _seed_test_data()

    yield
    import os
    for f in ["test_bcd.db", "test_questionnaire.db"]:
        if os.path.exists(f):
            os.unlink(f)


def _seed_test_data():
    from backend.src.models.models import Hospital, Role, User
    session = TestSession()
    if session.query(Hospital).first():
        session.close()
        return

    session.add(Hospital(id=1, name="TestHospital", contact_person="Dr. Test", email="test@hospital.com"))
    session.add(Hospital(id=2, name="Test1", contact_person="Super Admin", email="super@test1.com"))
    for name in ["Admin", "Doctor", "Staff"]:
        session.add(Role(name=name))
    session.commit()

    admin_role = session.query(Role).filter(Role.name == "Admin").first()
    doctor_role = session.query(Role).filter(Role.name == "Doctor").first()
    staff_role = session.query(Role).filter(Role.name == "Staff").first()

    session.add(User(email="admin@test.com", password_hash=get_password_hash("password123"), hospital_id=1, role_id=admin_role.id, is_active=True, full_name="Admin User"))
    session.add(User(email="doctor@test.com", password_hash=get_password_hash("password123"), hospital_id=1, role_id=doctor_role.id, is_active=True, full_name="Dr. Test"))
    session.add(User(email="staff@test.com", password_hash=get_password_hash("password123"), hospital_id=1, role_id=staff_role.id, is_active=True, full_name="Staff User"))
    session.commit()
    session.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_questionnaire_db] = override_get_questionnaire_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_hospital_and_user():
    return {"hospital_id": 1, "hospital_name": "TestHospital"}


def get_token(role="Admin", email=None, hospital_id=1):
    if email is None:
        email = f"{role.lower()}@test.com"
    return create_access_token(data={"sub": email, "hospital_id": hospital_id, "role": role})
