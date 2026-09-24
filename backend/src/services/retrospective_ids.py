from sqlalchemy import func
from sqlalchemy.orm import Session
from ..models.retrospective_models import RetrospectiveUploadBatch, RetrospectiveCase


def _next_number(current_max: str, prefix: str) -> int:
    if current_max and current_max.startswith(prefix):
        return int(current_max[len(prefix):]) + 1
    return 1


def generate_batch_id(db: Session) -> str:
    prefix = "RETRO_BATCH_"
    current_max = db.query(func.max(RetrospectiveUploadBatch.upload_batch_id)).scalar()
    return f"{prefix}{_next_number(current_max, prefix):06d}"


def generate_case_id(db: Session) -> str:
    prefix = "RETRO_"
    current_max = db.query(func.max(RetrospectiveCase.retrospective_case_id)).scalar()
    return f"{prefix}{_next_number(current_max, prefix):06d}"


def generate_case_ids(db: Session, count: int) -> list:
    """
    Bulk id allocation for large manifests (3,000+ cases): a single MAX()
    query up front, then increment in Python, instead of one query per case.
    """
    if count <= 0:
        return []
    prefix = "RETRO_"
    current_max = db.query(func.max(RetrospectiveCase.retrospective_case_id)).scalar()
    start = _next_number(current_max, prefix)
    return [f"{prefix}{start + i:06d}" for i in range(count)]
