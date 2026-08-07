from sqlalchemy import Column, Float, Integer, String, ForeignKey, Boolean, TIMESTAMP, UniqueConstraint, text, Text, Enum, JSON, Index, Date, DateTime
from sqlalchemy.orm import relationship
from ..db.session import Base
import enum

class QuestionResponseType(str, enum.Enum):
    text_field = "text_field"
    option = "option"
    numbers_only = "numbers_only"

class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(String(20), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    short_name = Column(String(20), nullable=True)
    contact_person = Column(String(50), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    address = Column(Text)
    pincode = Column(String(10))
    state = Column(String(100))
    type = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    users = relationship("User", back_populates="hospital")
    machines = relationship("Machine", back_populates="hospital", cascade="all, delete-orphan")  # renamed + uselist implicit True

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(String(20), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    hospital_short_name = Column(String(255), nullable=True)
    machine = Column(String(255), nullable=False)
    make = Column(String(255), nullable=True)
    technology = Column(String(255), nullable=True)
    no_of_machines = Column(Integer, default=1)
    hospital = relationship("Hospital", back_populates="machines")
class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)

    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email_hospital_role", "email", "hospital_id", "role_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(String(20), ForeignKey("hospitals.id"))
    role_id = Column(Integer, ForeignKey("roles.id"))
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)

    hospital = relationship("Hospital", back_populates="users")
    role = relationship("Role", back_populates="users")

class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String(50), nullable=False, unique=True)
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    description = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

class EmailTemplateCc(Base):
    __tablename__ = "email_template_cc"

    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String(50), ForeignKey("email_templates.template_key", ondelete="CASCADE"), nullable=False)
    cc_email = Column(String(255), nullable=False)

class ReminderEmailLog(Base):
    __tablename__ = "reminder_email_log"
    __table_args__ = (
        Index("uq_reminder_idempotency_key", "idempotency_key", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(20), nullable=False, default="hospital")
    hospital_id = Column(String(20), ForeignKey("hospitals.id"), nullable=True, index=True)
    recipient_email = Column(String(255), nullable=False)
    idempotency_key = Column(String(500), nullable=False)
    report_date = Column(Date, nullable=False)
    quarter_start = Column(Date, nullable=False)
    quarter_end = Column(Date, nullable=False)
    data_points = Column(Integer, nullable=False)
    lifetime_data_points = Column(Integer, nullable=False, default=0)
    assessments_submitted = Column(Integer, nullable=False)
    pending_submissions = Column(Integer, nullable=False)
    quarterly_target = Column(Integer, nullable=False, default=200)
    missing_questionnaire_sessions = Column(Integer, nullable=False, default=0)
    missing_consent = Column(Integer, nullable=False, default=0)
    missing_birads = Column(Integer, nullable=False, default=0)
    missing_density = Column(Integer, nullable=False, default=0)
    incomplete_assessments = Column(Integer, nullable=False, default=0)
    missing_mammogram_views = Column(Integer, nullable=False, default=0)
    missing_mammogram_reports = Column(Integer, nullable=False, default=0)
    mammogram_quality_flags = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text)
    failure_notified_at = Column(DateTime)
    failure_notification_error = Column(Text)
    sent_at = Column(DateTime)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    hospital = relationship("Hospital")


class ReminderConfiguration(Base):
    __tablename__ = "reminder_configuration"

    id = Column(Integer, primary_key=True)
    is_paused = Column(Boolean, nullable=False, default=False)
    is_disabled = Column(Boolean, nullable=False, default=False)
    updated_by = Column(String(255))
    updated_at = Column(DateTime)

class Language(Base):
    __tablename__ = "languages"

    code = Column(String(5), primary_key=True)
    name = Column(String(50), nullable=False)

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    section = Column(String(100))
    response_type = Column(Enum("text_field", "option", "numbers_only"), nullable=False)
    input_type = Column(String(50))
    is_required = Column(Boolean, default=False)
    min_value = Column(String(50), nullable=True)
    max_value = Column(String(50), nullable=True)
    placeholder = Column(String(255), nullable=True)
    question = Column(Text, nullable=True)
    parent_question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    trigger_answer = Column(String(255), nullable=True)

    translations = relationship("QuestionTranslation", back_populates="question")
    options = relationship("QuestionOption", back_populates="question")

class QuestionTranslation(Base):
    __tablename__ = "question_translations"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    language_code = Column(String(5), ForeignKey("languages.code"), nullable=False)
    question_text = Column(Text, nullable=False)

    question = relationship("Question", back_populates="translations")

class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    option_value = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)

    question = relationship("Question", back_populates="options")
    translations = relationship("QuestionOptionTranslation", back_populates="option")

class QuestionOptionTranslation(Base):
    __tablename__ = "question_option_translations"

    id = Column(Integer, primary_key=True, index=True)
    option_id = Column(Integer, ForeignKey("question_options.id", ondelete="CASCADE"), nullable=False)
    language_code = Column(String(5), ForeignKey("languages.code"), nullable=False)
    option_label = Column(Text, nullable=False)

    option = relationship("QuestionOption", back_populates="translations")

class PatientSession(Base):
    __tablename__ = "patient_sessions"

    id = Column(String(20), primary_key=True, index=True)
    hospital_id = Column(String(20), ForeignKey("hospitals.id"))
    consent_scanned_url = Column(Text)
    consent_timestamp = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    hospital = relationship("Hospital")
    responses = relationship("PatientResponse", back_populates="session", cascade="all, delete-orphan")
    assessments = relationship("DoctorAssessment", back_populates="session")

class PatientResponse(Base):
    __tablename__ = "patient_responses"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(String(20), ForeignKey("hospitals.id"), nullable=False)
    session_id = Column(String(20), ForeignKey("patient_sessions.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    hospital = relationship("Hospital")
    session = relationship("PatientSession", back_populates="responses")

class DoctorAssessment(Base):
    __tablename__ = "doctor_assessments"

    id = Column(Integer, primary_key=True, index=True)
    patient_session_id = Column(String(20), ForeignKey("patient_sessions.id", ondelete="CASCADE"), nullable=False)
    hospital_id = Column(String(20), ForeignKey("hospitals.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    questionnaire_feedback = Column(Text)
    is_questionnaire_correct = Column(Boolean, default=False)
    mammo_birads = Column(Enum('0', '1', '2', '3', '4', '5', '6'))
    mammo_density = Column(Enum('A', 'B', 'C', 'D'))
    us_biopsy_birads = Column(Enum('0', '1', '2', '3', '4', '5', '6'))
    us_biopsy_density = Column(Enum('A', 'B', 'C', 'D'))
    precision_diagnosis = Column(Enum('4A','4B','4C'))
    datapoint_feedback = Column(Text)
    clinical_findings = Column(JSON)
    recommendation_followup = Column(Text)
    routine_views_uploaded = Column(Boolean, default=False)
    doctor_risk_class = Column(String(50))
    doctor_case_notes = Column(Text)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    session = relationship("PatientSession")
    hospital = relationship("Hospital")
    doctor = relationship("User")
    attachments = relationship("Attachment", back_populates="assessment", cascade="all, delete-orphan")

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("doctor_assessments.id", ondelete="CASCADE"), nullable=False)
    file_type = Column(String(50), nullable=False)  # e.g., 'mammo_dicom', 'us_video'
    file_name = Column(String(255), nullable=False)
    storage_url = Column(Text, nullable=False)
    mime_type = Column(String(100))
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    assessment = relationship("DoctorAssessment", back_populates="attachments")


class MRMCStudy(Base):
    __tablename__ = "mrmc_studies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    hospital_id = Column(String(20), ForeignKey("hospitals.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    hospital = relationship("Hospital")
    creator = relationship("User")
    participants = relationship("MRMCStudyParticipant", back_populates="study", cascade="all, delete-orphan")


class MRMCStudyParticipant(Base):
    __tablename__ = "mrmc_study_participants"
    __table_args__ = (
        UniqueConstraint("study_id", "user_id", name="uq_study_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    study_id = Column(Integer, ForeignKey("mrmc_studies.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_reader = Column(Boolean, nullable=False, default=False)
    is_arbiter = Column(Boolean, nullable=False, default=False)
    assigned_count = Column(Integer, nullable=False, default=0)
    submitted_count = Column(Integer, nullable=False, default=0)
    kappa_score = Column(Float, nullable=True)

    study = relationship("MRMCStudy", back_populates="participants")
    user = relationship("User")