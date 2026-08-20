from pydantic import BaseModel


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