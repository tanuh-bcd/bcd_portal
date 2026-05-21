from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models.models import User, Hospital, Role
from ..schemas.schemas import Token, LoginRequest, HospitalResponse, TokenData
from ..core.security import verify_password, create_access_token
from ..core.config import settings
from typing import List

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # DEBUG: Validating token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        hospital_id: int = payload.get("hospital_id")
        role: str = payload.get("role")
        if email is None:
            raise credentials_exception
        
        # Get user ID from DB if not in token
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise credentials_exception
            
        token_data = {"email": email, "hospital_id": hospital_id, "role": role, "id": user.id}
    except JWTError:
        raise credentials_exception
    except Exception:
        raise credentials_exception
    return token_data

@router.get("/hospitals", response_model=List[HospitalResponse])
def get_hospitals(db: Session = Depends(get_db)):
    return db.query(Hospital).all()

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    # 1. Find Hospital
    hospital = db.query(Hospital).filter(Hospital.name == login_data.hospital_name).first()
    if not hospital:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid hospital name",
        )

    # 2. Find Role
    role = db.query(Role).filter(Role.name == login_data.role).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role",
        )

    # 3. Find User
    user = db.query(User).filter(
        User.email == login_data.email,
        User.hospital_id == hospital.id,
        User.role_id == role.id
    ).first()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    # 4. Create Token
    access_token = create_access_token(
        data={"sub": user.email, "hospital_id": user.hospital_id, "role": role.name}
    )
    return {"access_token": access_token, "token_type": "bearer", "full_name": user.full_name or ""}

@router.post("/reset-password")
def reset_password(email_data: dict):
    # This is a placeholder as per the blueprint
    return {"msg": f"Password reset email sent to {email_data.get('email')}"}
