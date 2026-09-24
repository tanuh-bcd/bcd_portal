from pydantic import BaseModel
from typing import Optional, List, Literal
import datetime

BatchStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]
CaseStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "PARTIAL", "FAILED", "NO_DATA"]
FileType = Literal["DICOM", "REPORT"]
FileUploadStatus = Literal["PENDING", "UPLOADED", "FAILED"]


class RetrospectiveUploadBatchCreate(BaseModel):
    institute_id: str
    institute_name: str
    source_folder_name: str
    created_by: Optional[str] = None


class RetrospectiveUploadBatchResponse(BaseModel):
    id: int
    upload_batch_id: str
    institute_id: str
    institute_name: str
    source_folder_name: str
    total_cases_identified: int
    processed_cases: int
    successful_cases: int
    failed_cases: int
    no_data_cases: int
    batch_status: BatchStatus
    created_by: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class RetrospectiveCaseCreate(BaseModel):
    upload_batch_id: str
    institute_id: str
    institute_name: str
    source_case_name: str
    source_folder: Optional[str] = None


class RetrospectiveFileResponse(BaseModel):
    id: int
    retrospective_case_id: str
    file_type: FileType
    file_name: str
    gcp_path: Optional[str] = None
    dicom_uid: Optional[str] = None
    upload_status: FileUploadStatus
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class RetrospectiveCaseResponse(BaseModel):
    id: int
    retrospective_case_id: str
    upload_batch_id: str
    institute_id: str
    institute_name: str
    source_case_name: str
    source_folder: Optional[str] = None
    dicom_count: int
    report_count: int
    dicom_available: bool
    report_available: bool
    dicom_reference: Optional[str] = None
    report_gcs_path: Optional[str] = None
    case_status: CaseStatus
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class RetrospectiveCaseDetailResponse(RetrospectiveCaseResponse):
    files: List[RetrospectiveFileResponse] = []


class RetrospectiveBatchProgress(BaseModel):
    upload_batch_id: str
    batch_status: BatchStatus
    total_cases_identified: int
    processed_cases: int
    successful_cases: int
    failed_cases: int
    no_data_cases: int
    progress_percent: float


# --- Folder manifest upload -------------------------------------------------
# The browser walks the selected folder client-side and posts this manifest
# (names only, no bytes) to create batch/case/file records up front. Each
# file's actual bytes are then uploaded separately via signed URL, the same
# two-phase pattern the existing patient/doctor upload flow uses.

class RetrospectiveFileManifestItem(BaseModel):
    file_type: FileType
    file_name: str


class RetrospectiveCaseManifestItem(BaseModel):
    source_case_name: str
    source_folder: Optional[str] = None
    files: List[RetrospectiveFileManifestItem] = []


class RetrospectiveBatchManifestCreate(BaseModel):
    source_folder_name: str
    cases: List[RetrospectiveCaseManifestItem]


class RetrospectiveFileManifestResult(BaseModel):
    id: int
    file_type: FileType
    file_name: str
    upload_status: FileUploadStatus


class RetrospectiveCaseManifestResult(BaseModel):
    retrospective_case_id: str
    source_case_name: str
    case_status: CaseStatus
    files: List[RetrospectiveFileManifestResult] = []


class RetrospectiveBatchManifestResponse(BaseModel):
    batch: RetrospectiveUploadBatchResponse
    cases: List[RetrospectiveCaseManifestResult]


class RetrospectiveUploadUrlResponse(BaseModel):
    upload_url: str
    gcs_url: str
    blob_path: str
    file_id: int


class RetrospectiveUploadCompleteRequest(BaseModel):
    gcs_url: str
    dicom_uid: Optional[str] = None


class RetrospectiveUploadFailedRequest(BaseModel):
    error_message: str


class RetrospectiveRetryFileItem(BaseModel):
    id: int
    retrospective_case_id: str
    source_case_name: str
    file_type: FileType
    file_name: str
    upload_status: FileUploadStatus


class RetrospectiveRetryResponse(BaseModel):
    batch: RetrospectiveUploadBatchResponse
    files_to_retry: List[RetrospectiveRetryFileItem]


class RetrospectiveDashboardCount(BaseModel):
    institute_id: str
    institute_name: str
    total_retrospective_cases: int
