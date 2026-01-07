from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..models.models import PatientSession, Question, QuestionTranslation, QuestionOption, QuestionOptionTranslation, PatientResponse, DoctorAssessment, Attachment
from ..schemas.schemas import QuestionResponse, QuestionOptionResponse, QuestionnaireSubmission, PatientSessionListItem, PatientSessionDetail, DoctorAssessmentCreate, DoctorAssessmentResponse
from ..core.config import settings
from .auth import get_current_user
from google.cloud import storage
from typing import List, Optional
import uuid
import datetime
import pytz
import json

router = APIRouter()

def get_ist_now():
    return datetime.datetime.now(pytz.timezone('Asia/Kolkata'))

def upload_to_gcs(file_content, destination_blob_name):
    if not settings.GCP_STORAGE_BUCKET:
        raise Exception("GCP_STORAGE_BUCKET not configured")
    
    if settings.GOOGLE_APPLICATION_CREDENTIALS and settings.GOOGLE_APPLICATION_CREDENTIALS.strip():
        storage_client = storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
    else:
        storage_client = storage.Client()
        
    bucket = storage_client.bucket(settings.GCP_STORAGE_BUCKET)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(file_content, content_type="application/octet-stream")
    return f"gs://{settings.GCP_STORAGE_BUCKET}/{destination_blob_name}"

@router.get("/questions", response_model=List[QuestionResponse])
def get_questions(lang: str = "en", db: Session = Depends(get_db)):
    questions = db.query(Question).all()
    
    response = []
    for q in questions:
        # Get translation for the question
        trans = db.query(QuestionTranslation).filter(
            QuestionTranslation.question_id == q.id,
            QuestionTranslation.language_code == lang
        ).first()
        
        # Fallback to English if translation not found
        if not trans and lang != "en":
             trans = db.query(QuestionTranslation).filter(
                QuestionTranslation.question_id == q.id,
                QuestionTranslation.language_code == "en"
            ).first()
        
        if not trans:
            continue
            
        options = []
        for opt in q.options:
            opt_trans = db.query(QuestionOptionTranslation).filter(
                QuestionOptionTranslation.option_id == opt.id,
                QuestionOptionTranslation.language_code == lang
            ).first()
            
            # Fallback to English
            if not opt_trans and lang != "en":
                opt_trans = db.query(QuestionOptionTranslation).filter(
                    QuestionOptionTranslation.option_id == opt.id,
                    QuestionOptionTranslation.language_code == "en"
                ).first()
            
            if opt_trans:
                options.append(QuestionOptionResponse(
                    id=opt.id,
                    option_value=opt.option_value,
                    option_label=opt_trans.option_label,
                    sort_order=opt.sort_order
                ))
        
        response.append(QuestionResponse(
            id=q.id,
            section=q.section,
            response_type=q.response_type,
            question_text=trans.question_text,
            parent_question_id=q.parent_question_id,
            trigger_answer=q.trigger_answer,
            options=sorted(options, key=lambda x: x.sort_order)
        ))
    
    return response

@router.post("/consent")
async def upload_consent(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
             raise HTTPException(status_code=400, detail="User hospital ID not found")

        content = await file.read()
        
        # Create a unique filename
        ist_now = get_ist_now()
        timestamp = ist_now.strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        destination_blob_name = f"consents/{hospital_id}/{timestamp}_{unique_id}.{extension}"
        
        gcs_url = upload_to_gcs(content, destination_blob_name)
        
        # Save to DB
        new_session = PatientSession(
            hospital_id=hospital_id,
            consent_scanned_url=gcs_url,
            consent_timestamp=ist_now
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return {"id": new_session.id, "consent_scanned_url": gcs_url}
        
    except Exception as e:
        print(f"Error uploading consent: {e}")
        error_detail = str(e)
        if "403" in error_detail:
            error_detail = "Permission denied: Service account does not have write access to GCS bucket."
        elif "not configured" in error_detail:
            error_detail = "GCS bucket is not configured in settings."
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not upload consent: {error_detail}"
        )

@router.post("/questionnaire")
async def submit_questionnaire(
    submission: QuestionnaireSubmission,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
            raise HTTPException(status_code=400, detail="User hospital ID not found")
        
        # Verify session exists and belongs to the hospital
        session = db.query(PatientSession).filter(
            PatientSession.id == submission.session_id,
            PatientSession.hospital_id == hospital_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Patient session not found")
        
        # Save responses
        for resp in submission.responses:
            new_response = PatientResponse(
                hospital_id=hospital_id,
                session_id=submission.session_id,
                question=resp.question,
                answer=resp.answer
            )
            db.add(new_response)
        
        db.commit()
        return {"status": "success", "message": "Questionnaire responses saved"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving questionnaire: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save questionnaire responses: {str(e)}"
        )

@router.post("/assessment", response_model=DoctorAssessmentResponse)
async def create_doctor_assessment(
    patient_session_id: int = Form(...),
    questionnaire_feedback: Optional[str] = Form(None),
    is_questionnaire_correct: bool = Form(False),
    mammo_birads: Optional[str] = Form(None),
    mammo_density: Optional[str] = Form(None),
    us_biopsy_birads: Optional[str] = Form(None),
    us_biopsy_density: Optional[str] = Form(None),
    precision_diagnosis: Optional[str] = Form(None),
    datapoint_feedback: Optional[str] = Form(None),
    mammo_dicom: List[UploadFile] = File([]),
    mammo_reading: Optional[UploadFile] = File(None),
    us_video: Optional[UploadFile] = File(None),
    us_reading: Optional[UploadFile] = File(None),
    biopsy_doc: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        hospital_id = current_user.get("hospital_id")
        doctor_id = current_user.get("id")
        
        if not hospital_id or not doctor_id:
            raise HTTPException(status_code=400, detail="User hospital ID or doctor ID not found")
            
        # Verify session
        session = db.query(PatientSession).filter(
            PatientSession.id == patient_session_id,
            PatientSession.hospital_id == hospital_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Patient session not found")
            
        # Create Assessment
        assessment = DoctorAssessment(
            patient_session_id=patient_session_id,
            hospital_id=hospital_id,
            doctor_id=doctor_id,
            questionnaire_feedback=questionnaire_feedback,
            is_questionnaire_correct=is_questionnaire_correct,
            mammo_birads=mammo_birads,
            mammo_density=mammo_density,
            us_biopsy_birads=us_biopsy_birads,
            us_biopsy_density=us_biopsy_density,
            precision_diagnosis=precision_diagnosis,
            datapoint_feedback=datapoint_feedback
        )
        db.add(assessment)
        db.flush() # Get assessment ID
        
        ist_now = get_ist_now()
        timestamp = ist_now.strftime("%Y%m%d_%H%M%S")
        
        async def handle_upload(file: UploadFile, file_type: str):
            content = await file.read()
            unique_id = uuid.uuid4().hex[:6]
            extension = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
            # Rename file with file_type
            new_filename = f"{file_type}_{timestamp}_{unique_id}.{extension}"
            destination_blob_name = f"assessments/{hospital_id}/{patient_session_id}/{new_filename}"
            
            gcs_url = upload_to_gcs(content, destination_blob_name)
            
            attachment = Attachment(
                assessment_id=assessment.id,
                file_type=file_type,
                file_name=file.filename,
                storage_url=gcs_url,
                mime_type=file.content_type
            )
            db.add(attachment)
            return attachment

        # Handle DICOMs (multiple)
        for dicom_file in mammo_dicom:
            if dicom_file.filename:
                await handle_upload(dicom_file, "mammo_dicom")
        
        # Handle other single uploads
        if mammo_reading and mammo_reading.filename:
            await handle_upload(mammo_reading, "mammo_reading")
        
        if us_video and us_video.filename:
            # The requirement mentioned us_image/video for renaming, but file_type should probably match the schema
            await handle_upload(us_video, "us_video")
            
        if us_reading and us_reading.filename:
            await handle_upload(us_reading, "us_reading")
            
        if biopsy_doc and biopsy_doc.filename:
            # Requirement says rename with biopsy_reading for biopsy_doc? 
            # "Rename the files with the file_type like mammo_dicom, us_image/video, biopsy_reading, us_reading, mammo_reading."
            await handle_upload(biopsy_doc, "biopsy_reading")

        db.commit()
        db.refresh(assessment)
        return assessment

    except Exception as e:
        print(f"Error saving doctor assessment: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save doctor assessment: {str(e)}"
        )
