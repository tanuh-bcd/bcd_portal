from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

QcBase = declarative_base()

class QcRole(QcBase):
    __tablename__ = "qc_roles"

    qc_id = Column(Integer, primary_key=True, autoincrement=True)
    qc_name = Column(String(50), unique=True, nullable=False)

class QcHospital(QcBase):
    __tablename__ = "qc_hospitals"

    qc_id = Column(String(20), primary_key=True)
    qc_name = Column(String(255), nullable=False)

class QcUser(QcBase):
    __tablename__ = "qc_users"

    qc_id = Column(Integer, primary_key=True, autoincrement=True)
    qc_role_id = Column(Integer, ForeignKey("qc_roles.qc_id"), nullable=True)
    qc_email = Column(String(255), nullable=False)
    qc_password_hash = Column(String(255), nullable=False)
    qc_full_name = Column(String(255), nullable=True)
    qc_is_active = Column(Boolean, default=True)
    qc_hospital_id = Column(String(20), ForeignKey("qc_hospitals.qc_id"), nullable=True)

    role = relationship("QcRole")