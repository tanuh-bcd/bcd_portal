from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import List

from ...db.Qualitycheck.qc_session import get_qc_db
from ...models.Qualitycheck.qc_models import QcUser, QcRole, QcDoctorAssessment, QcAssignment, QcAssignmentStatus
from ...schemas.Qualitycheck.qc_schema import (
    QcAssignmentBatchResponse, QcUserResponse, QcSubjectResponse, QcAssignmentCreate, QcAssignmentResponse
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


@router.post("/assignments", response_model=QcAssignmentBatchResponse)
def create_assignments(
    payload: QcAssignmentCreate,
    db: Session = Depends(get_qc_db),
    current=Depends(get_current_qc_user),
):
    if not payload.assessment_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No subjects selected")

    user = db.query(QcUser).filter(QcUser.qc_id == payload.radiologist_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    assessments = db.query(QcDoctorAssessment).filter(
        QcDoctorAssessment.qc_id.in_(payload.assessment_ids)
    ).all()
    found_ids = {a.qc_id for a in assessments}
    missing_ids = set(payload.assessment_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subjects not found: {sorted(missing_ids)}"
        )

    existing = db.query(QcAssignment).filter(
        QcAssignment.qc_assessment_id.in_(payload.assessment_ids),
        QcAssignment.qc_radiologist_id == payload.radiologist_id,
    ).all()
    already_assigned_ids = {e.qc_assessment_id for e in existing}

    assigned_by_user = db.query(QcUser).filter(QcUser.qc_email == current["email"]).first()

    new_assignments = []
    for assessment_id in payload.assessment_ids:
        if assessment_id in already_assigned_ids:
            continue
        assignment = QcAssignment(
            qc_assessment_id=assessment_id,
            qc_radiologist_id=payload.radiologist_id,
            qc_assigned_by=assigned_by_user.qc_id if assigned_by_user else None,
            qc_status=QcAssignmentStatus.pending,
        )
        db.add(assignment)
        new_assignments.append(assignment)

    user.qc_assigned = payload.assigned == "yes"

    db.commit()
    for a in new_assignments:
        db.refresh(a)

    return QcAssignmentBatchResponse(
        created=[QcAssignmentResponse(qc_id=a.qc_id, qc_status=a.qc_status.value) for a in new_assignments],
        skipped=sorted(already_assigned_ids),
    )