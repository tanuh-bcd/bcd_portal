import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db.session import get_db, get_questionnaire_db, get_retrospective_db
from ..mammogram_service import get_portal_mammogram_dashboard
from ..models.retrospective_models import RetrospectiveCase
from ..services.retrospective_processing import REPORT_ONLY_CASE

router = APIRouter()
logger = logging.getLogger(__name__)

def _get_retrospective_case_count(retro_db: Session) -> int:
    """
    Matches the "Total Retrospective Case Count" shown in the Admin's Upload
    History (sum of each batch's total_cases_identified): every identified
    case counts regardless of case_status (PENDING/PROCESSING/FAILED/...),
    only report-only cases are excluded -- same rule as recompute_batch_progress.
    """
    try:
        return retro_db.query(RetrospectiveCase).filter(~REPORT_ONLY_CASE).count()
    except Exception as e:
        logger.warning(f"Could not compute retrospective case count: {e}")
        return 0

@router.get("/portal-stats")
def get_mammogram_portal_stats(
    app_db: Session = Depends(get_db),
    questionnaire_db: Session = Depends(get_questionnaire_db),
    retro_db: Session = Depends(get_retrospective_db),
):
    retrospective_case_count = _get_retrospective_case_count(retro_db)
    try:
        return get_portal_mammogram_dashboard(app_db, questionnaire_db, retrospective_case_count=retrospective_case_count)
    except Exception as e:
        logger.error(f"Error computing portal mammogram stats: {e}")
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