from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import List

from ...db.Qualitycheck.qc_session import get_qc_db
from ...models.Qualitycheck.qc_models import QcUser, QcRole, QcDoctorAssessment, QcAssignment, QcAssignmentStatus
from ...schemas.Qualitycheck.qc_schema import (
    QcUserResponse, QcSubjectResponse, QcAssignmentCreate, QcAssignmentResponse
)
from ...core.config import settings

router = APIRouter()

qc_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/qc-login")


async def get_current_qc_user(token: str = Depends(qc_oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")
        if email is None:
            raise credentials_exception
        return {"email": email, "role": role}
    except JWTError:
        raise credentials_exception


@router.get("/users", response_model=List[QcUserResponse])
def get_qc_users(db: Session = Depends(get_qc_db), _current=Depends(get_current_qc_user)):
    return (
        db.query(QcUser)
        .join(QcRole, QcUser.qc_role_id == QcRole.qc_id)
        .filter(QcRole.qc_name != "Admin")
        .all()
    )


@router.get("/subjects", response_model=List[QcSubjectResponse])
def get_qc_subjects(db: Session = Depends(get_qc_db), _current=Depends(get_current_qc_user)):
    assessments = db.query(QcDoctorAssessment).order_by(QcDoctorAssessment.qc_id).all()
    return [
        QcSubjectResponse(
            qc_id=a.qc_id,
            display_id=a.qc_sub_ui_id or f"QC_{a.qc_id:05d}",
            qc_patient_session_id=a.qc_patient_session_id,
            qc_created_at=a.qc_created_at,
        )
        for a in assessments
    ]


@router.post("/assignments", response_model=QcAssignmentResponse)
def create_assignment(
    payload: QcAssignmentCreate,
    db: Session = Depends(get_qc_db),
    current=Depends(get_current_qc_user),
):
    assessment = db.query(QcDoctorAssessment).filter(QcDoctorAssessment.qc_id == payload.assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    user = db.query(QcUser).filter(QcUser.qc_id == payload.radiologist_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.query(QcAssignment).filter(
        QcAssignment.qc_assessment_id == payload.assessment_id,
        QcAssignment.qc_radiologist_id == payload.radiologist_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already assigned to this user")

    assigned_by_user = db.query(QcUser).filter(QcUser.qc_email == current["email"]).first()

    assignment = QcAssignment(
        qc_assessment_id=payload.assessment_id,
        qc_radiologist_id=payload.radiologist_id,
        qc_assigned_by=assigned_by_user.qc_id if assigned_by_user else None,
        qc_status=QcAssignmentStatus.pending,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment