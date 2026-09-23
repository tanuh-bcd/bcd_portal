import os
import re
import unicodedata

from google.cloud import storage

from ..core.config import settings

RETRO_GCS_PREFIX = settings.RETROSPECTIVE_GCS_PREFIX or "retrospective"

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
