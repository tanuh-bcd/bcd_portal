import logging
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from google.api_core.exceptions import NotFound
from google.cloud import storage

from ..core.config import settings

logger = logging.getLogger(__name__)

RETRO_GCS_PREFIX = settings.RETROSPECTIVE_GCS_PREFIX or "retrospective"
# Up to this many cases are looked up by their own folder; beyond it the whole
# retrospective prefix is listed once, which is fewer calls for a big batch.
_LIST_PER_CASE_LIMIT = 25
_DELETE_WORKERS = 16

_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


class RetrospectivePathError(ValueError):
    pass


def _sanitize_segment(segment: str, label: str) -> str:
    if not segment:
        raise RetrospectivePathError(f"{label} must not be empty")
    normalized = unicodedata.normalize("NFKC", segment).strip()
    if normalized in ("", ".", ".."):
        raise RetrospectivePathError(f"{label} is not a valid path segment")
    if "/" in normalized or "\\" in normalized or "\x00" in normalized:
        raise RetrospectivePathError(f"{label} must not contain path separators")
    if not _SAFE_SEGMENT_RE.match(normalized):
        raise RetrospectivePathError(f"{label} contains unsupported characters: {segment!r}")
    return normalized


def _assert_within_retrospective_root(blob_path: str) -> str:
    normalized = os.path.normpath(blob_path)
    root = f"{RETRO_GCS_PREFIX}/"
    if normalized != blob_path or not normalized.startswith(root):
        raise RetrospectivePathError(
            f"Resolved path {normalized!r} escapes the {root!r} prefix"
        )
    return normalized


def sanitize_file_name(file_name: str) -> str:
    """
    Strips any directory components a client claims (defeats path traversal
    by discarding them, not by rejecting the request) and validates what's
    left. Callers should persist this sanitized value, not the raw input --
    it's what actually ends up in the GCS blob path.
    """
    basename = file_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return _sanitize_segment(basename, "file_name")


def build_retrospective_case_prefix(retrospective_case_id: str) -> str:
    case_id = _sanitize_segment(retrospective_case_id, "retrospective_case_id")
    if not case_id.startswith("RETRO_") or case_id.startswith("RETRO_BATCH_"):
        raise RetrospectivePathError("retrospective_case_id must look like RETRO_XXXXXX")
    prefix = f"{RETRO_GCS_PREFIX}/{case_id}"
    return _assert_within_retrospective_root(prefix)


def build_retrospective_blob_path(retrospective_case_id: str, file_type: str, file_name: str) -> str:
    """
    DICOM files go under <case>/DICOM/<name>; reports go directly under
    <case>/<name>, matching the existing BCD folder convention.
    """
    case_prefix = build_retrospective_case_prefix(retrospective_case_id)
    safe_name = sanitize_file_name(file_name)

    ft = (file_type or "").upper()
    if ft == "DICOM":
        blob_path = f"{case_prefix}/DICOM/{safe_name}"
    elif ft == "REPORT":
        blob_path = f"{case_prefix}/{safe_name}"
    else:
        raise RetrospectivePathError(f"Unsupported file_type: {file_type!r}")

    return _assert_within_retrospective_root(blob_path)


def _get_storage_client():
    return storage.Client()


def upload_retrospective_file(file_content: bytes, blob_path: str, content_type: str = "application/octet-stream") -> str:
    if not settings.GCP_STORAGE_BUCKET:
        raise Exception("GCP_STORAGE_BUCKET not configured")
    _assert_within_retrospective_root(blob_path)

    client = _get_storage_client()
    bucket = client.bucket(settings.GCP_STORAGE_BUCKET)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(file_content, content_type=content_type)
    return f"gs://{settings.GCP_STORAGE_BUCKET}/{blob_path}"


def delete_case_objects(bucket, case_ids, known_paths=()):
    """Delete everything stored in the bucket for these cases, whatever upload
    status the database holds for it. A file can be in the bucket while the
    database says PENDING or FAILED (the browser never reported completion),
    so the case's folder is listed instead of trusting the status.

    known_paths (paths recorded in the database) are deleted too. Only objects
    under the retrospective prefix are ever touched. Returns
    (objects_deleted, failed_paths)."""
    root = f"{RETRO_GCS_PREFIX}/"
    prefixes = tuple(f"{build_retrospective_case_prefix(case_id)}/" for case_id in case_ids)

    names = {path for path in known_paths if path and path.startswith(root)}
    if len(prefixes) <= _LIST_PER_CASE_LIMIT:
        for prefix in prefixes:
            names.update(blob.name for blob in bucket.list_blobs(prefix=prefix))
    else:
        names.update(blob.name for blob in bucket.list_blobs(prefix=root) if blob.name.startswith(prefixes))

    def _delete(name):
        try:
            bucket.blob(name).delete()
            return name, True, None
        except NotFound:
            return name, False, None
        except Exception as e:
            return name, False, e

    deleted, failures = 0, []
    with ThreadPoolExecutor(max_workers=_DELETE_WORKERS) as pool:
        for name, was_deleted, error in pool.map(_delete, sorted(names)):
            if was_deleted:
                deleted += 1
            elif error is not None:
                logger.warning("Failed to delete retrospective GCS object %s: %s", name, error)
                failures.append(name)
    return deleted, failures
