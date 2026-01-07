from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..db.session import get_db
from ..models.models import User, Hospital, Role
from ..schemas.schemas import UserCreate, HospitalCreate, User as UserSchema, HospitalResponse
from ..core.security import get_password_hash
from .auth import get_current_user

router = APIRouter()

def check_admin_role(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user_role = current_user.get("role", "")
    if not user_role or user_role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    
    # Check if the admin belongs to Test1 hospital for certain operations
    hospital_id = current_user.get("hospital_id")
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if hospital:
        current_user["hospital_name"] = hospital.name
        
    return current_user

def check_super_admin(current_user: dict = Depends(check_admin_role)):
    if current_user.get("hospital_name") != "Test1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation is only allowed for Test1 hospital admins",
        )
    return current_user

@router.post("/hospitals", response_model=HospitalResponse)
def create_hospital(
    hospital_in: HospitalCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(check_super_admin)
):
    hospital = db.query(Hospital).filter(Hospital.email == hospital_in.email).first()
    if hospital:
        raise HTTPException(
            status_code=400,
            detail="A hospital with this email already exists.",
        )
    db_hospital = Hospital(
        name=hospital_in.name,
        contact_person=hospital_in.contact_person,
        email=hospital_in.email,
        address=hospital_in.address
    )
    db.add(db_hospital)
    db.commit()
    db.refresh(db_hospital)
    return db_hospital

@router.post("/users", response_model=UserSchema)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(check_admin_role)
):
    # If trying to create an Admin, only Test1 admin can do it
    role = db.query(Role).filter(Role.id == user_in.role_id).first()
    if role and role.name.lower() == 'admin':
        if current_user.get("hospital_name") != "Test1":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Test1 hospital admins can create other admin accounts",
            )

    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists.",
        )
    
    # Verify hospital exists
    hospital = db.query(Hospital).filter(Hospital.id == user_in.hospital_id).first()
    if not hospital:
        raise HTTPException(
            status_code=404,
            detail="Hospital not found.",
        )
    
    # Verify role exists
    role = db.query(Role).filter(Role.id == user_in.role_id).first()
    if not role:
        raise HTTPException(
            status_code=404,
            detail="Role not found.",
        )

    db_user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        hospital_id=user_in.hospital_id,
        role_id=user_in.role_id,
        is_active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/roles")
def get_roles(
    db: Session = Depends(get_db),
    current_user: dict = Depends(check_admin_role)
):
    return db.query(Role).all()
