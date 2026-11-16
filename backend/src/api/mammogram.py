import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db.session import get_db, get_questionnaire_db
from ..core.cache import cached
from ..core.config import settings
from ..mammogram_service import get_portal_mammogram_dashboard
from ..services.retrospective_storage import count_source_bucket_cases

router = APIRouter()
logger = logging.getLogger(__name__)

def _get_retrospective_case_count() -> int:
    if not settings.RETROSPECTIVE_SOURCE_BUCKET:
        return 0
    try:
        result = count_source_bucket_cases(settings.RETROSPECTIVE_SOURCE_BUCKET)
        return int(result.get("total_case_count") or 0)
    except Exception as e:
        logger.warning(f"Could not compute retrospective case count: {e}")
        return 0

@router.get("/portal-stats")
def get_mammogram_portal_stats(
    app_db: Session = Depends(get_db),
    questionnaire_db: Session = Depends(get_questionnaire_db),
):
    try:
        return cached("portal-stats", lambda: get_portal_mammogram_dashboard(
            app_db, questionnaire_db,
            retrospective_case_count=_get_retrospective_case_count(),
        ))
    except Exception as e:
        logger.error(f"Error computing portal mammogram stats: {e}")
        retrospective_case_count = _get_retrospective_case_count()
        return {
            "totalAssessments": 0,
            "totals": {"imaging_studies": 0, "reports": 0, "total": 0},
            "viewTypeCounts": [],
            "setCompleteness": [],
            "reportCompleteness": [],
            "completionRate": {"viewsUploaded": 0, "totalSubjects": 0, "rate": 0.0},
            "byHospital": [],
            "hospitalTypeBreakdown": [],
            "reportsByHospital": [],
            "biradsByInstituteAndSide": [],
            "assessmentInstitutesCount": 0,
            "assessmentStatesCount": 0,
            "retrospectiveCaseCount": retrospective_case_count,
            "error": str(e),
        }