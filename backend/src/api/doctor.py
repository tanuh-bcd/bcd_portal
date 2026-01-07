from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models.models import PatientSession
from ..schemas.schemas import PatientSessionListItem, PatientSessionDetail
from .auth import get_current_user
from typing import List

router = APIRouter()

@router.get("/sessions", response_model=List[PatientSessionListItem])
def get_patient_sessions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user.get("hospital_id")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="User hospital ID not found")
    
    sessions = db.query(PatientSession).filter(
        PatientSession.hospital_id == hospital_id
    ).order_by(PatientSession.consent_timestamp.desc()).all()
    
    return sessions

@router.get("/sessions/{session_id}", response_model=PatientSessionDetail)
def get_patient_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user.get("hospital_id")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="User hospital ID not found")
    
    session = db.query(PatientSession).filter(
        PatientSession.id == session_id,
        PatientSession.hospital_id == hospital_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Patient session not found")
    
    return session
