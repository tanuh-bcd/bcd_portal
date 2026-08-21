from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class QcLoginRequest(BaseModel):
    role: str
    email: str
    password: str


class QcToken(BaseModel):
    access_token: str
    token_type: str
    full_name: str


class QcRoleResponse(BaseModel):
    qc_id: int
    qc_name: str

    class Config:
        from_attributes = True


class QcUserResponse(BaseModel):
    qc_id: int
    qc_full_name: Optional[str] = None
    qc_email: str

    class Config:
        from_attributes = True


class QcSubjectResponse(BaseModel):
    qc_id: int
    display_id: str
    qc_patient_session_id: Optional[str] = None
    qc_created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


from typing import List, Literal

class QcAssignmentCreate(BaseModel):
    assessment_ids: List[int]
    radiologist_id: int
    assigned: Literal["yes", "no"] = "no"


class QcAssignmentBatchResponse(BaseModel):
    created: List[QcAssignmentResponse]
    skipped: List[int]

class QcAssignmentResponse(BaseModel):
    qc_id: int
    qc_status: str

    class Config:
        from_attributes = True