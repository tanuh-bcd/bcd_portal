from typing import Optional
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from ..models.retrospective_models import RetrospectiveCase, RetrospectiveUploadBatch

# A case whose manifest never included any DICOM file at all (report only) no
# longer counts as a valid retrospective case, and is hidden from case lists
# and every count -- as if it doesn't exist. Based on file composition
# (dicom_count/report_count), not upload outcome, so a case with DICOM files
# that are merely pending/failed stays visible and retriable rather than
# disappearing.
REPORT_ONLY_CASE = and_(RetrospectiveCase.dicom_count == 0, RetrospectiveCase.report_count > 0)


def recompute_case_rollup(case: RetrospectiveCase, files: Optional[list] = None) -> None:
    """
    Derives case_status and the dicom/report availability flags purely from
    its file rows. Must run after any file's upload_status changes.

    PENDING    = nothing has been attempted yet (fresh from manifest creation).
    PROCESSING = at least one file is still pending an upload attempt.
    COMPLETED  = every file resolved, at least one uploaded, none failed.
    PARTIAL    = every file resolved, at least one uploaded AND at least one failed.
    FAILED     = every file resolved, none uploaded (all failed).
    NO_DATA    = the case had no files to begin with (never counts as a case).

    `files` lets bulk callers (manifest creation for 3,000+ cases) pass the
    rows they already hold in memory instead of triggering a lazy-load query
    per case.
    """
    files = case.files if files is None else files
    if not files:
        case.case_status = "NO_DATA"
        case.dicom_available = False
        case.report_available = False
        case.dicom_count = 0
        case.report_count = 0
        return

    uploaded = [f for f in files if f.upload_status == "UPLOADED"]
    failed = [f for f in files if f.upload_status == "FAILED"]
    pending = [f for f in files if f.upload_status == "PENDING"]

    dicom_uploaded = [f for f in uploaded if f.file_type == "DICOM"]
    report_uploaded = [f for f in uploaded if f.file_type == "REPORT"]

    case.dicom_count = len([f for f in files if f.file_type == "DICOM"])
    case.report_count = len([f for f in files if f.file_type == "REPORT"])
    case.dicom_available = len(dicom_uploaded) > 0
    case.report_available = len(report_uploaded) > 0
    case.dicom_reference = ",".join(f.gcp_path for f in dicom_uploaded) if dicom_uploaded else None
    case.report_gcs_path = report_uploaded[0].gcp_path if report_uploaded else None

    if pending and not uploaded and not failed:
        case.case_status = "PENDING"
    elif pending:
        case.case_status = "PROCESSING"
    elif uploaded and failed:
        case.case_status = "PARTIAL"
    elif uploaded:
        case.case_status = "COMPLETED"
        case.error_message = None
    else:
        case.case_status = "FAILED"
        case.error_message = "; ".join(f.error_message or f"{f.file_name} failed" for f in failed) or case.error_message


def recompute_batch_progress(db: Session, batch: RetrospectiveUploadBatch) -> None:
    counts = dict(
        db.query(RetrospectiveCase.case_status, func.count(RetrospectiveCase.id))
        .filter(
            RetrospectiveCase.upload_batch_id == batch.upload_batch_id,
            ~REPORT_ONLY_CASE,
        )
        .group_by(RetrospectiveCase.case_status)
        .all()
    )
    total = sum(counts.values())
    no_data = counts.get("NO_DATA", 0)
    failed = counts.get("FAILED", 0)
    partial = counts.get("PARTIAL", 0)
    successful = counts.get("COMPLETED", 0) + partial
    still_open = counts.get("PENDING", 0) + counts.get("PROCESSING", 0)

    batch.total_cases_identified = total
    batch.processed_cases = total - still_open
    batch.successful_cases = successful
    batch.failed_cases = failed
    batch.no_data_cases = no_data

    if still_open > 0:
        batch.batch_status = "PROCESSING" if batch.processed_cases > 0 else "PENDING"
    elif failed > 0 and successful == 0:
        batch.batch_status = "FAILED"
    elif failed > 0 or partial > 0:
        batch.batch_status = "COMPLETED_WITH_ERRORS"
    else:
        batch.batch_status = "COMPLETED"
