from pydantic import BaseModel, EmailStr
from typing import Optional, List
import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    hospital_id: int
    role_id: int

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    hospital_id: Optional[int] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    hospital_name: str
    role: str
    email: EmailStr
    password: str

class HospitalBase(BaseModel):
    name: str
    contact_person: str
    email: EmailStr
    address: Optional[str] = None

class HospitalCreate(HospitalBase):
    pass

class HospitalResponse(HospitalBase):
    id: int

    class Config:
        from_attributes = True

class LanguageResponse(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True

class QuestionOptionResponse(BaseModel):
    id: int
    option_value: str
    option_label: str
    sort_order: int

    class Config:
        from_attributes = True

class QuestionResponse(BaseModel):
    id: int
    section: str
    response_type: str
    question_text: str
    parent_question_id: Optional[int] = None
    trigger_answer: Optional[str] = None
    options: list[QuestionOptionResponse] = []

    class Config:
        from_attributes = True

class PatientResponseCreate(BaseModel):
    question: str
    answer: str

class PatientResponse(PatientResponseCreate):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class PatientSessionListItem(BaseModel):
    id: int
    consent_scanned_url: Optional[str] = None
    consent_timestamp: datetime.datetime

    class Config:
        from_attributes = True

class PatientSessionDetail(PatientSessionListItem):
    responses: list[PatientResponse] = []

    class Config:
        from_attributes = True

class QuestionnaireSubmission(BaseModel):
    session_id: int
    responses: list[PatientResponseCreate]

class DoctorAssessmentCreate(BaseModel):
    patient_session_id: int
    questionnaire_feedback: Optional[str] = None
    is_questionnaire_correct: bool = False
    mammo_birads: Optional[str] = None
    mammo_density: Optional[str] = None
    us_biopsy_birads: Optional[str] = None
    us_biopsy_density: Optional[str] = None
    precision_diagnosis: Optional[str] = None
    datapoint_feedback: Optional[str] = None

class AttachmentResponse(BaseModel):
    id: int
    file_type: str
    file_name: str
    storage_url: str
    mime_type: Optional[str] = None

    class Config:
        from_attributes = True

class DoctorAssessmentResponse(BaseModel):
    id: int
    patient_session_id: int
    hospital_id: int
    doctor_id: int
    questionnaire_feedback: Optional[str] = None
    is_questionnaire_correct: bool
    mammo_birads: Optional[str] = None
    mammo_density: Optional[str] = None
    us_biopsy_birads: Optional[str] = None
    us_biopsy_density: Optional[str] = None
    precision_diagnosis: Optional[str] = None
    datapoint_feedback: Optional[str] = None
    created_at: datetime.datetime
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True
