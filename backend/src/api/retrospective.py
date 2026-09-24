from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import logging

from ..db.session import get_retrospective_db
from ..core.config import settings
from ..models.retrospective_models import RetrospectiveUploadBatch, RetrospectiveCase, RetrospectiveFile
from ..schemas.retrospective_schemas import (
    RetrospectiveBatchManifestCreate,
    RetrospectiveBatchManifestResponse,
    RetrospectiveCaseManifestResult,
    RetrospectiveFileManifestResult,
    RetrospectiveUploadBatchResponse,
    RetrospectiveCaseResponse,
    RetrospectiveCaseDetailResponse,
    RetrospectiveUploadUrlResponse,
    RetrospectiveUploadCompleteRequest,
    RetrospectiveUploadFailedRequest,
    RetrospectiveRetryResponse,
    RetrospectiveRetryFileItem,
    RetrospectiveDashboardCount,
)
from ..services.retrospective_ids import generate_batch_id, generate_case_ids
from ..services.retrospective_processing import (
    recompute_case_rollup,
    recompute_batch_progress,
    REPORT_ONLY_CASE,
)
from ..services.retrospective_storage import (
    RetrospectivePathError,
    build_retrospective_blob_path,
    sanitize_file_name,
)
from .admin import check_super_admin
from google.cloud import storage

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_storage_client():
    return storage.Client()


def _case_to_manifest_result(case: RetrospectiveCase, files) -> RetrospectiveCaseManifestResult:
    return RetrospectiveCaseManifestResult(
        retrospective_case_id=case.retrospective_case_id,
        source_case_name=case.source_case_name,
        case_status=case.case_status,
        files=[
            RetrospectiveFileManifestResult(
                id=f.id, file_type=f.file_type, file_name=f.file_name, upload_status=f.upload_status
            )
            for f in files
        ],
    )


@router.post("/batches", response_model=RetrospectiveBatchManifestResponse)
def create_batch(
    manifest: RetrospectiveBatchManifestCreate,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    if not manifest.cases:
        raise HTTPException(status_code=400, detail="Manifest must include at least one case")

    institute_id = current_user["hospital_id"]
    institute_name = current_user.get("hospital_name") or "Test"

    # Duplicate prevention (spec section 21): a folder name that was already
    # uploaded for this institute is rejected outright rather than silently
    # merged case-by-case. Retrying a partially-failed upload goes through
    # POST /batches/{id}/retry against the original batch, not a new upload.
    existing = (
        db.query(RetrospectiveUploadBatch)
        .filter(
            RetrospectiveUploadBatch.institute_id == institute_id,
            RetrospectiveUploadBatch.source_folder_name == manifest.source_folder_name,
        )
        .order_by(RetrospectiveUploadBatch.id.desc())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Folder '{manifest.source_folder_name}' was already uploaded as batch "
                f"{existing.upload_batch_id} (status: {existing.batch_status}). "
                "Use 'Retry Failed' on that batch instead of uploading it again."
            ),
        )

    # Same check at the case level: a case subfolder name that was already
    # uploaded under a DIFFERENT top-level folder (or any other prior batch)
    # is also rejected outright, not silently re-processed.
    incoming_case_names = [c.source_case_name for c in manifest.cases]
    dupes = (
        db.query(RetrospectiveCase.source_case_name, RetrospectiveCase.retrospective_case_id, RetrospectiveCase.upload_batch_id)
        .filter(
            RetrospectiveCase.institute_id == institute_id,
            RetrospectiveCase.source_case_name.in_(incoming_case_names),
        )
        .all()
    )
    if dupes:
        detail = "; ".join(
            f"'{name}' already exists as {case_id} in batch {batch_id}"
            for name, case_id, batch_id in dupes
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Some case folder(s) were already uploaded before: {detail}.",
        )

    batch = RetrospectiveUploadBatch(
        upload_batch_id=generate_batch_id(db),
        institute_id=institute_id,
        institute_name=institute_name,
        source_folder_name=manifest.source_folder_name,
        created_by=current_user.get("email"),
    )
    db.add(batch)
    db.flush()

    case_ids = generate_case_ids(db, len(manifest.cases))
    case_results = []

    for case_item, retro_case_id in zip(manifest.cases, case_ids):
        case = RetrospectiveCase(
            retrospective_case_id=retro_case_id,
            upload_batch_id=batch.upload_batch_id,
            institute_id=institute_id,
            institute_name=institute_name,
            source_case_name=case_item.source_case_name,
            source_folder=case_item.source_folder,
        )
        db.add(case)
        db.flush()

        file_rows = []
        for file_item in case_item.files:
            try:
                safe_name = sanitize_file_name(file_item.file_name)
                blob_path = build_retrospective_blob_path(retro_case_id, file_item.file_type, safe_name)
                file_rows.append(RetrospectiveFile(
                    retrospective_case_id=case.retrospective_case_id,
                    file_type=file_item.file_type,
                    file_name=safe_name,
                    gcp_path=blob_path,
                    upload_status="PENDING",
                ))
            except RetrospectivePathError as e:
                file_rows.append(RetrospectiveFile(
                    retrospective_case_id=case.retrospective_case_id,
                    file_type=file_item.file_type,
                    file_name=file_item.file_name,
                    gcp_path=None,
                    upload_status="FAILED",
                    error_message=str(e),
                ))

        db.add_all(file_rows)
        db.flush()

        recompute_case_rollup(case, files=file_rows)
        case_results.append(_case_to_manifest_result(case, file_rows))

    recompute_batch_progress(db, batch)
    db.commit()
    db.refresh(batch)

    return RetrospectiveBatchManifestResponse(
        batch=RetrospectiveUploadBatchResponse.model_validate(batch),
        cases=case_results,
    )


@router.get("/batches", response_model=List[RetrospectiveUploadBatchResponse])
def list_batches(
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    institute_id = current_user["hospital_id"]
    batches = (
        db.query(RetrospectiveUploadBatch)
        .filter(RetrospectiveUploadBatch.institute_id == institute_id)
        .order_by(RetrospectiveUploadBatch.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # Self-heal: a batch's summary is normally kept current by whatever last
    # touched one of its files, but nothing re-runs that for a batch that
    # never gets a new event (e.g. one written before a rollup bug fix
    # shipped). Recomputing on every read is cheap at admin-tool volumes and
    # guarantees GETs always reflect the cases' actual state.
    for batch in batches:
        recompute_batch_progress(db, batch)
    db.commit()
    return batches


def _get_batch_or_404(db: Session, institute_id: str, upload_batch_id: str) -> RetrospectiveUploadBatch:
    batch = db.query(RetrospectiveUploadBatch).filter(
        RetrospectiveUploadBatch.upload_batch_id == upload_batch_id,
        RetrospectiveUploadBatch.institute_id == institute_id,
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.get("/batches/{upload_batch_id}", response_model=RetrospectiveUploadBatchResponse)
def get_batch(
    upload_batch_id: str,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    batch = _get_batch_or_404(db, current_user["hospital_id"], upload_batch_id)
    recompute_batch_progress(db, batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches/{upload_batch_id}/cases", response_model=List[RetrospectiveCaseResponse])
def list_batch_cases(
    upload_batch_id: str,
    case_status: Optional[str] = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    _get_batch_or_404(db, current_user["hospital_id"], upload_batch_id)
    query = db.query(RetrospectiveCase).filter(
        RetrospectiveCase.upload_batch_id == upload_batch_id,
        ~REPORT_ONLY_CASE,
    )
    if case_status:
        query = query.filter(RetrospectiveCase.case_status == case_status.upper())
    return query.order_by(RetrospectiveCase.id).offset(offset).limit(limit).all()


@router.get("/cases/{retrospective_case_id}", response_model=RetrospectiveCaseDetailResponse)
def get_case(
    retrospective_case_id: str,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    case = (
        db.query(RetrospectiveCase)
        .options(joinedload(RetrospectiveCase.files))
        .filter(
            RetrospectiveCase.retrospective_case_id == retrospective_case_id,
            RetrospectiveCase.institute_id == current_user["hospital_id"],
            ~REPORT_ONLY_CASE,
        )
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


def _get_pending_file_or_404(db: Session, institute_id: str, file_id: int) -> RetrospectiveFile:
    file_row = (
        db.query(RetrospectiveFile)
        .join(RetrospectiveCase, RetrospectiveFile.retrospective_case_id == RetrospectiveCase.retrospective_case_id)
        .filter(RetrospectiveFile.id == file_id, RetrospectiveCase.institute_id == institute_id)
        .first()
    )
    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")
    return file_row


@router.post("/files/{file_id}/upload-url", response_model=RetrospectiveUploadUrlResponse)
def generate_retrospective_upload_url(
    file_id: int,
    request: Request,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    file_row = _get_pending_file_or_404(db, current_user["hospital_id"], file_id)
    if not file_row.gcp_path:
        raise HTTPException(status_code=400, detail="This file failed validation and has no storage path")
    if not settings.GCP_STORAGE_BUCKET:
        raise HTTPException(status_code=500, detail="GCP_STORAGE_BUCKET not configured")

    origin = request.headers.get("origin", "")
    try:
        client = _get_storage_client()
        bucket = client.bucket(settings.GCP_STORAGE_BUCKET)
        blob = bucket.blob(file_row.gcp_path)
        upload_url = blob.create_resumable_upload_session(
            content_type="application/octet-stream",
            origin=origin,
        )
    except Exception as e:
        logger.warning("Failed to create retrospective upload session: %s", e)
        raise HTTPException(status_code=500, detail=f"Could not generate upload URL: {str(e)}")

    gcs_url = f"gs://{settings.GCP_STORAGE_BUCKET}/{file_row.gcp_path}"
    return RetrospectiveUploadUrlResponse(
        upload_url=upload_url, gcs_url=gcs_url, blob_path=file_row.gcp_path, file_id=file_row.id
    )


@router.post("/files/{file_id}/upload-complete", response_model=RetrospectiveCaseResponse)
def mark_file_uploaded(
    file_id: int,
    body: RetrospectiveUploadCompleteRequest,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    institute_id = current_user["hospital_id"]
    file_row = _get_pending_file_or_404(db, institute_id, file_id)
    file_row.upload_status = "UPLOADED"
    file_row.error_message = None
    file_row.dicom_uid = body.dicom_uid
    db.flush()

    case = db.query(RetrospectiveCase).options(joinedload(RetrospectiveCase.files)).filter(
        RetrospectiveCase.retrospective_case_id == file_row.retrospective_case_id
    ).first()
    recompute_case_rollup(case)
    batch = db.query(RetrospectiveUploadBatch).filter(
        RetrospectiveUploadBatch.upload_batch_id == case.upload_batch_id
    ).first()
    recompute_batch_progress(db, batch)
    db.commit()
    db.refresh(case)
    return case


@router.post("/files/{file_id}/upload-failed", response_model=RetrospectiveCaseResponse)
def mark_file_failed(
    file_id: int,
    body: RetrospectiveUploadFailedRequest,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    institute_id = current_user["hospital_id"]
    file_row = _get_pending_file_or_404(db, institute_id, file_id)
    file_row.upload_status = "FAILED"
    file_row.error_message = body.error_message
    db.flush()

    case = db.query(RetrospectiveCase).options(joinedload(RetrospectiveCase.files)).filter(
        RetrospectiveCase.retrospective_case_id == file_row.retrospective_case_id
    ).first()
    recompute_case_rollup(case)
    batch = db.query(RetrospectiveUploadBatch).filter(
        RetrospectiveUploadBatch.upload_batch_id == case.upload_batch_id
    ).first()
    recompute_batch_progress(db, batch)
    db.commit()
    db.refresh(case)
    return case


@router.post("/batches/{upload_batch_id}/retry", response_model=RetrospectiveRetryResponse)
def retry_failed_cases(
    upload_batch_id: str,
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    institute_id = current_user["hospital_id"]
    batch = _get_batch_or_404(db, institute_id, upload_batch_id)

    # Covers two situations with one action: files that actually FAILED, and
    # files that are still PENDING because the browser session that created
    # them never got to upload them at all (tab closed mid-upload, hard
    # refresh, etc). Both need the same thing -- the admin reselects the
    # folder and whatever isn't UPLOADED yet gets sent again.
    unresolved_cases = (
        db.query(RetrospectiveCase)
        .options(joinedload(RetrospectiveCase.files))
        .filter(
            RetrospectiveCase.upload_batch_id == upload_batch_id,
            RetrospectiveCase.case_status.in_(["FAILED", "PARTIAL", "PENDING", "PROCESSING"]),
        )
        .all()
    )

    retry_items = []
    for case in unresolved_cases:
        for file_row in case.files:
            if file_row.upload_status == "FAILED":
                if not file_row.gcp_path:
                    # Failed validation at manifest time (e.g. bad filename) --
                    # there is no path to retry against; the admin needs to fix
                    # the source file and re-upload it as part of a new case.
                    continue
                file_row.upload_status = "PENDING"
                file_row.error_message = None
            elif file_row.upload_status != "PENDING":
                continue  # already UPLOADED, nothing to do

            retry_items.append(RetrospectiveRetryFileItem(
                id=file_row.id,
                retrospective_case_id=case.retrospective_case_id,
                source_case_name=case.source_case_name,
                file_type=file_row.file_type,
                file_name=file_row.file_name,
                upload_status=file_row.upload_status,
            ))
        # Derive status from the files themselves rather than forcing a value --
        # a case with nothing retriable (e.g. all its failures are unfixable
        # invalid filenames) must resolve back to FAILED/PARTIAL immediately,
        # not sit in "PROCESSING" forever with no event left to unstick it.
        recompute_case_rollup(case)
    db.flush()
    recompute_batch_progress(db, batch)
    db.commit()
    db.refresh(batch)

    return RetrospectiveRetryResponse(
        batch=RetrospectiveUploadBatchResponse.model_validate(batch),
        files_to_retry=retry_items,
    )


@router.get("/dashboard-count", response_model=RetrospectiveDashboardCount)
def get_dashboard_count(
    db: Session = Depends(get_retrospective_db),
    current_user: dict = Depends(check_super_admin),
):
    institute_id = current_user["hospital_id"]
    total = (
        db.query(RetrospectiveCase)
        .filter(
            RetrospectiveCase.institute_id == institute_id,
            RetrospectiveCase.dicom_available == True,  # noqa: E712 -- report-only cases never count
        )
        .count()
    )
    return RetrospectiveDashboardCount(
        institute_id=institute_id,
        institute_name=current_user.get("hospital_name") or "Test",
        total_retrospective_cases=total,
    )
