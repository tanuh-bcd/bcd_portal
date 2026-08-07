from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..db.session import get_db
from ..models.models import MRMCStudy, MRMCStudyParticipant, User, Hospital, Role, Machine
from ..schemas.schemas import MRMCParticipantResponse, MRMCStudyCreate, MRMCStudyResponse, UserCreate, HospitalCreate, User as UserSchema, HospitalResponse, MachineCreate, MachineResponse,ClinicianOption
from ..core.security import get_password_hash
from ..core.email import send_template_email
from .auth import get_current_user

router = APIRouter()

def check_admin_role(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user_role = current_user.get("role", "")
    if not user_role or user_role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user does not have enough privileges",
        )
    
    # Check if the admin belongs to Test hospital for certain operations
    hospital_id = current_user.get("hospital_id")
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if hospital:
        current_user["hospital_name"] = hospital.name
        
    return current_user

def check_super_admin(current_user: dict = Depends(check_admin_role)):
    if current_user.get("hospital_name") != "Test":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation is only allowed for Test hospital admins",
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
    from sqlalchemy import func
    max_id = db.query(func.max(Hospital.id)).scalar()
    if max_id and max_id.startswith("clinic_"):
        num = int(max_id.split("_")[1]) + 1
    else:
        num = 1
    new_id = f"clinic_{num:05d}"

    db_hospital = Hospital(
        id=new_id,
        name=hospital_in.name,
        short_name=hospital_in.short_name,
        contact_person=hospital_in.contact_person,
        email=hospital_in.email,
        address=hospital_in.address,
        pincode=hospital_in.pincode,
        state=hospital_in.state,
        type=hospital_in.type
    )
    db.add(db_hospital)
    db.commit()
    db.refresh(db_hospital)

    try:
        send_template_email(db, "hospital_added", hospital_in.email, {
            "hospital_name": hospital_in.name,
            "contact_person": hospital_in.contact_person,
            "contact_email": hospital_in.email,
            "address": hospital_in.address or "",
        })
    except Exception:
        pass

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
        if current_user.get("hospital_name") != "Test":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Test hospital admins can create other admin accounts",
            )

    user = db.query(User).filter(
        User.email == user_in.email,
        User.hospital_id == user_in.hospital_id,
        User.role_id == user_in.role_id
    ).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email, hospital, and role already exists.",
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

    try:
        send_template_email(db, "user_created", user_in.email, {
            "full_name": user_in.full_name or user_in.email,
            "email": user_in.email,
            "hospital_name": hospital.name,
            "role_name": role.name,
            "temp_password": user_in.password,
        })
    except Exception:
        pass

    return db_user

@router.get("/roles")
def get_roles(
    db: Session = Depends(get_db),
    current_user: dict = Depends(check_admin_role)
):
    return db.query(Role).all()


@router.post("/machines", response_model=MachineResponse)
def create_machine(
    machine_in: MachineCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(check_admin_role)
):
    hospital = db.query(Hospital).filter(Hospital.id == machine_in.hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found.")

    if current_user.get("hospital_name") != "Test" and current_user.get("hospital_id") != machine_in.hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create machine details for your own institution.",
        )

    if machine_in.hospital_short_name and hospital.short_name and machine_in.hospital_short_name != hospital.short_name:
        raise HTTPException(
            status_code=400,
            detail="Hospital short name does not match the selected institute.",
        )

    db_machine = Machine(
        hospital_id=machine_in.hospital_id,
        hospital_short_name=machine_in.hospital_short_name or hospital.short_name,
        machine=machine_in.machine,
        make=machine_in.make,
        technology=machine_in.technology,
        no_of_machines=machine_in.no_of_machines
    )
    db.add(db_machine)
    db.commit()
    db.refresh(db_machine)
    return db_machine

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "Admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

@router.post("/mrmc-studies", response_model=MRMCStudyResponse)
def create_mrmc_study(
    data: MRMCStudyCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    if data.arbiter_user_id in data.reader_user_ids:
        raise HTTPException(
            status_code=400,
            detail="A user cannot be assigned as both reader and arbiter"
        )
    if not data.reader_user_ids:
        raise HTTPException(status_code=400, detail="At least one reader is required")

    study = MRMCStudy(
        name=data.name,
        hospital_id=current_user["hospital_id"],
        created_by=current_user["id"]
    )
    db.add(study)
    db.flush()  # populates study.id before commit

    for uid in data.reader_user_ids:
        db.add(MRMCStudyParticipant(
            study_id=study.id,
            user_id=uid,
            is_reader=True,
            assigned_count=1
        ))
    db.add(MRMCStudyParticipant(
        study_id=study.id,
        user_id=data.arbiter_user_id,
        is_arbiter=True,
        assigned_count=1
    ))

    db.commit()
    db.refresh(study)
    return study

@router.get("/mrmc-studies/participants", response_model=List[MRMCParticipantResponse])
def get_study_participants(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    rows = (
        db.query(MRMCStudyParticipant, User.full_name)
        .join(User, MRMCStudyParticipant.user_id == User.id)
        .join(MRMCStudy, MRMCStudyParticipant.study_id == MRMCStudy.id)
        .filter(MRMCStudy.hospital_id == current_user["hospital_id"])
        .all()
    )

    aggregated = {}
    for p, full_name in rows:
        entry = aggregated.setdefault(p.user_id, {
            "user_id": p.user_id,
            "full_name": full_name,
            "is_reader": False,
            "is_arbiter": False,
            "assigned_count": 0,
            "submitted_count": 0,
            "kappa_scores": []
        })
        entry["is_reader"] = entry["is_reader"] or p.is_reader
        entry["is_arbiter"] = entry["is_arbiter"] or p.is_arbiter
        entry["assigned_count"] += p.assigned_count or 0
        entry["submitted_count"] += p.submitted_count or 0
        if p.kappa_score is not None:
            entry["kappa_scores"].append(p.kappa_score)

    return [
        MRMCParticipantResponse(
            user_id=e["user_id"],
            full_name=e["full_name"],
            is_reader=e["is_reader"],
            is_arbiter=e["is_arbiter"],
            assigned_count=e["assigned_count"],
            submitted_count=e["submitted_count"],
            kappa_score=(sum(e["kappa_scores"]) / len(e["kappa_scores"])) if e["kappa_scores"] else None
        )
        for e in aggregated.values()
    ]
@router.get("/users/clinicians", response_model=List[ClinicianOption])
def get_clinicians(
    db: Session = Depends(get_db),
    current_user: dict = Depends(check_admin_role)
):
    clinicians = (
        db.query(User.id, User.full_name)
        .filter(User.role_id == 2, User.hospital_id == current_user["hospital_id"])
        .order_by(User.full_name)
        .all()
    )
    return [ClinicianOption(id=u.id, full_name=u.full_name) for u in clinicians]
