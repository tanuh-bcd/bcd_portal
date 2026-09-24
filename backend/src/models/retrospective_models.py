from sqlalchemy import Column, Integer, String, Boolean, Text, TIMESTAMP, Enum, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db.session import RetrospectiveBase

class RetrospectiveUploadBatch(RetrospectiveBase):
    __tablename__ = "retrospective_upload_batches"

    id = Column(Integer, primary_key=True, index=True)
    upload_batch_id = Column(String(30), nullable=False, unique=True, index=True)
    institute_id = Column(String(20), nullable=False, index=True)
    institute_name = Column(String(255), nullable=False)
    source_folder_name = Column(String(255), nullable=False)
    total_cases_identified = Column(Integer, nullable=False, default=0)
    processed_cases = Column(Integer, nullable=False, default=0)
    successful_cases = Column(Integer, nullable=False, default=0)
    failed_cases = Column(Integer, nullable=False, default=0)
    no_data_cases = Column(Integer, nullable=False, default=0)
    batch_status = Column(
        Enum("PENDING", "PROCESSING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"),
        nullable=False,
        default="PENDING",
    )
    created_by = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        default=func.now(),
        onupdate=func.now(),
    )

    cases = relationship(
        "RetrospectiveCase",
        back_populates="batch",
        cascade="all, delete-orphan",
        primaryjoin="RetrospectiveUploadBatch.upload_batch_id==RetrospectiveCase.upload_batch_id",
        foreign_keys="[RetrospectiveCase.upload_batch_id]",
    )


class RetrospectiveCase(RetrospectiveBase):
    __tablename__ = "retrospective_cases"
    __table_args__ = (
        UniqueConstraint("upload_batch_id", "source_case_name", name="uq_retro_case_batch_source"),
        Index("idx_retro_case_status", "case_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    retrospective_case_id = Column(String(20), nullable=False, unique=True, index=True)
    upload_batch_id = Column(
        String(30),
        ForeignKey("retrospective_upload_batches.upload_batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    institute_id = Column(String(20), nullable=False, index=True)
    institute_name = Column(String(255), nullable=False)
    source_case_name = Column(String(255), nullable=False)
    source_folder = Column(String(500), nullable=True)
    dicom_count = Column(Integer, nullable=False, default=0)
    report_count = Column(Integer, nullable=False, default=0)
    dicom_available = Column(Boolean, nullable=False, default=False)
    report_available = Column(Boolean, nullable=False, default=False)
    dicom_reference = Column(Text, nullable=True)
    report_gcs_path = Column(Text, nullable=True)
    case_status = Column(
        Enum("PENDING", "PROCESSING", "COMPLETED", "PARTIAL", "FAILED", "NO_DATA"),
        nullable=False,
        default="PENDING",
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        default=func.now(),
        onupdate=func.now(),
    )

    batch = relationship(
        "RetrospectiveUploadBatch",
        back_populates="cases",
        primaryjoin="RetrospectiveCase.upload_batch_id==RetrospectiveUploadBatch.upload_batch_id",
        foreign_keys=[upload_batch_id],
    )
    files = relationship(
        "RetrospectiveFile",
        back_populates="case",
        cascade="all, delete-orphan",
        primaryjoin="RetrospectiveCase.retrospective_case_id==RetrospectiveFile.retrospective_case_id",
        foreign_keys="[RetrospectiveFile.retrospective_case_id]",
    )


class RetrospectiveFile(RetrospectiveBase):
    __tablename__ = "retrospective_files"
    __table_args__ = (
        UniqueConstraint("retrospective_case_id", "file_type", "file_name", name="uq_retro_file_case_name"),
        Index("idx_retro_file_dicom_uid", "dicom_uid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    retrospective_case_id = Column(
        String(20),
        ForeignKey("retrospective_cases.retrospective_case_id", ondelete="CASCADE"),
        nullable=False,
    )
    file_type = Column(Enum("DICOM", "REPORT"), nullable=False)
    file_name = Column(String(255), nullable=False)
    gcp_path = Column(Text, nullable=True)
    dicom_uid = Column(String(128), nullable=True)
    upload_status = Column(Enum("PENDING", "UPLOADED", "FAILED"), nullable=False, default="PENDING")
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"), default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        default=func.now(),
        onupdate=func.now(),
    )

    case = relationship(
        "RetrospectiveCase",
        back_populates="files",
        primaryjoin="RetrospectiveFile.retrospective_case_id==RetrospectiveCase.retrospective_case_id",
        foreign_keys=[retrospective_case_id],
    )
