from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session, joinedload
from ..db.session import get_db, get_questionnaire_db
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
import time

router = APIRouter()

GCS_BASE_PREFIX = "tanuh-data-capture"

FILE_TYPE_MAP = {
    "mammo_dicom": "mammogram",
    "mammo_cc_left": "mammogram",
    "mammo_cc_right": "mammogram",
    "mammo_mlo_left": "mammogram",
    "mammo_mlo_right": "mammogram",
    "mammo_reading": "mammogram-report",
    "annot_cc_left": "annotation",
    "annot_cc_right": "annotation",
    "annot_mlo_left": "annotation",
    "annot_mlo_right": "annotation",
    "us_video": "ultrasound",
    "us_reading": "ultrasound-report",
    "biopsy_reading": "biopsy",
    "consent": "consent",
}

def get_ist_now():
    return datetime.datetime.now(pytz.timezone('Asia/Kolkata'))

def generate_subject_id(db):
    from sqlalchemy import func
    result = db.query(func.max(PatientSession.id)).scalar()
    if result and result.startswith("subject_"):
        num = int(result.split("_")[1]) + 1
    else:
        num = 1
    return f"subject_{num:05d}"

def build_blob_path(clinic_id, subject_id, file_type, original_filename, ist_now, seq=None):
    doc_type = FILE_TYPE_MAP.get(file_type, file_type)
    extension = original_filename.rsplit('.', 1)[-1] if '.' in original_filename else 'bin'
    upload_date = ist_now.strftime("%Y%m%d")
    detail = f"{file_type}-{seq}" if seq is not None else file_type
    doc_name = f"{clinic_id}_{subject_id}_{detail}_{upload_date}.{extension}"
    return f"{GCS_BASE_PREFIX}/{clinic_id}/{subject_id}/{doc_type}/{doc_name}"

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

def _get_storage_client():
    if settings.GOOGLE_APPLICATION_CREDENTIALS and settings.GOOGLE_APPLICATION_CREDENTIALS.strip():
        return storage.Client.from_service_account_json(settings.GOOGLE_APPLICATION_CREDENTIALS)
    return storage.Client()


@router.post("/upload-url")
def generate_upload_url(
    file_type: str = Form(...),
    file_name: str = Form(...),
    session_id: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user.get("hospital_id")
    if not hospital_id:
        raise HTTPException(status_code=400, detail="User hospital ID not found")

    ist_now = get_ist_now()
    blob_path = build_blob_path(hospital_id, session_id, file_type, file_name, ist_now)

    client = _get_storage_client()
    bucket = client.bucket(settings.GCP_STORAGE_BUCKET)
    blob = bucket.blob(blob_path)

    signed_url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(hours=1),
        method="PUT",
        content_type="application/octet-stream",
    )

    gcs_url = f"gs://{settings.GCP_STORAGE_BUCKET}/{blob_path}"
    return {
        "upload_url": signed_url,
        "gcs_url": gcs_url,
        "blob_path": blob_path,
    }


@router.post("/upload-complete")
def record_upload(
    session_id: str = Form(...),
    file_type: str = Form(...),
    file_name: str = Form(...),
    gcs_url: str = Form(...),
    mime_type: str = Form(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    hospital_id = current_user.get("hospital_id")
    doctor_id = current_user.get("id")

    assessment = db.query(DoctorAssessment).filter(
        DoctorAssessment.patient_session_id == session_id
    ).first()

    if not assessment:
        assessment = DoctorAssessment(
            patient_session_id=session_id,
            hospital_id=hospital_id,
            doctor_id=doctor_id,
        )
        db.add(assessment)
        db.flush()

    existing = db.query(Attachment).filter(
        Attachment.assessment_id == assessment.id,
        Attachment.file_type == file_type
    ).first()

    if existing:
        existing.file_name = file_name
        existing.storage_url = gcs_url
        existing.mime_type = mime_type
    else:
        db.add(Attachment(
            assessment_id=assessment.id,
            file_type=file_type,
            file_name=file_name,
            storage_url=gcs_url,
            mime_type=mime_type,
        ))

    db.commit()
    return {"success": True}


@router.get("/questions", response_model=List[QuestionResponse])
def get_questions(lang: str = "en", db: Session = Depends(get_db)):
    # Optimized query with joinedload to fetch translations and options in fewer queries
    questions = db.query(Question).options(
        joinedload(Question.translations),
        joinedload(Question.options).joinedload(QuestionOption.translations)
    ).order_by(Question.id).all()
    
    response = []
    for q in questions:
        # Find the translation for the requested language or fallback to English
        trans = next((t for t in q.translations if t.language_code == lang), None)
        if not trans and lang != "en":
            trans = next((t for t in q.translations if t.language_code == "en"), None)
        
        # Use q.question from questions table if lang is 'en' or translation is not found
        question_text = q.question if (lang == "en" and q.question) else (trans.question_text if trans else q.question)
        
        if not question_text:
            continue
            
        options = []
        for opt in q.options:
            opt_trans = next((t for t in opt.translations if t.language_code == lang), None)
            if not opt_trans and lang != "en":
                opt_trans = next((t for t in opt.translations if t.language_code == "en"), None)
            
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
            input_type=q.input_type,
            is_required=q.is_required,
            min_value=q.min_value,
            max_value=q.max_value,
            placeholder=q.placeholder,
            question_text=question_text,
            parent_question_id=q.parent_question_id,
            trigger_answer=q.trigger_answer,
            options=sorted(options, key=lambda x: x.sort_order)
        ))
    
    return response

@router.post("/consent")
async def upload_consent(
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    start_time = time.time()
    try:
        hospital_id = current_user.get("hospital_id")
        if not hospital_id:
             raise HTTPException(status_code=400, detail="User hospital ID not found")

        gcs_url = None
        ist_now = get_ist_now()

        subject_id = generate_subject_id(db)

        if file:
            content = await file.read()
            extension = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'jpg'
            upload_date = ist_now.strftime("%Y%m%d")
            consent_blob = f"{GCS_BASE_PREFIX}/consent/{hospital_id}_{subject_id}_consent_{upload_date}.{extension}"
            gcs_url = upload_to_gcs(content, consent_blob)

        new_session = PatientSession(
            id=subject_id,
            hospital_id=hospital_id,
            consent_scanned_url=gcs_url,
            consent_timestamp=ist_now
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        duration = time.time() - start_time
        print(f"Time taken for POST /api/v1/patient/consent: {duration:.4f} seconds")
        
        return {"id": new_session.id, "consent_scanned_url": gcs_url}
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"Time taken for POST /api/v1/patient/consent (FAILED): {duration:.4f} seconds")
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
    patient_session_id: str = Form(...),
    questionnaire_feedback: Optional[str] = Form(None),
    is_questionnaire_correct: bool = Form(False),
    mammo_birads: Optional[str] = Form(None),
    mammo_density: Optional[str] = Form(None),
    us_biopsy_birads: Optional[str] = Form(None),
    us_biopsy_density: Optional[str] = Form(None),
    precision_diagnosis: Optional[str] = Form(None),
    datapoint_feedback: Optional[str] = Form(None),
    clinical_findings: Optional[str] = Form(None),
    recommendation_followup: Optional[str] = Form(None),
    routine_views_uploaded: bool = Form(False),
    doctor_risk_class: Optional[str] = Form(None),
    doctor_case_notes: Optional[str] = Form(None),
    mammo_cc_left: Optional[UploadFile] = File(None),
    mammo_cc_right: Optional[UploadFile] = File(None),
    mammo_mlo_left: Optional[UploadFile] = File(None),
    mammo_mlo_right: Optional[UploadFile] = File(None),
    mammo_dicom: List[UploadFile] = File([]),
    mammo_reading: Optional[UploadFile] = File(None),
    us_video: Optional[UploadFile] = File(None),
    us_reading: Optional[UploadFile] = File(None),
    biopsy_doc: Optional[UploadFile] = File(None),
    annot_cc_left: Optional[UploadFile] = File(None),
    annot_cc_right: Optional[UploadFile] = File(None),
    annot_mlo_left: Optional[UploadFile] = File(None),
    annot_mlo_right: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    q_db: Session = Depends(get_questionnaire_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        hospital_id = current_user.get("hospital_id")
        doctor_id = current_user.get("id")
        user_role = current_user.get("role")

        if not hospital_id or not doctor_id:
            raise HTTPException(status_code=400, detail="User hospital ID or doctor ID not found")

        # Verify session exists in bcd_questionnaire
        from sqlalchemy import text as sql_text
        session_row = q_db.execute(sql_text(
            "SELECT session_id FROM session_table WHERE session_id = :sid"
        ), {"sid": patient_session_id}).fetchone()

        if not session_row:
            raise HTTPException(status_code=404, detail="Patient session not found")
            
        # Check if assessment already exists
        assessment = db.query(DoctorAssessment).filter(
            DoctorAssessment.patient_session_id == patient_session_id
        ).first()

        if assessment:
            # Check permissions: original doctor or hospital admin
            is_admin = user_role.lower() == 'admin'
            if assessment.doctor_id != doctor_id and not is_admin:
                raise HTTPException(status_code=403, detail="Not authorized to edit this assessment")
            
            assessment.questionnaire_feedback = questionnaire_feedback
            assessment.is_questionnaire_correct = is_questionnaire_correct
            assessment.mammo_birads = mammo_birads
            assessment.mammo_density = mammo_density
            assessment.us_biopsy_birads = us_biopsy_birads
            assessment.us_biopsy_density = us_biopsy_density
            assessment.precision_diagnosis = precision_diagnosis
            assessment.datapoint_feedback = datapoint_feedback
            assessment.clinical_findings = json.loads(clinical_findings) if clinical_findings else None
            assessment.recommendation_followup = recommendation_followup
            assessment.routine_views_uploaded = routine_views_uploaded
            assessment.doctor_risk_class = doctor_risk_class
            assessment.doctor_case_notes = doctor_case_notes
        else:
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
                datapoint_feedback=datapoint_feedback,
                clinical_findings=json.loads(clinical_findings) if clinical_findings else None,
                recommendation_followup=recommendation_followup,
                routine_views_uploaded=routine_views_uploaded,
                doctor_risk_class=doctor_risk_class,
                doctor_case_notes=doctor_case_notes,
            )
            db.add(assessment)
            db.flush() # Get assessment ID
        
        ist_now = get_ist_now()
        timestamp = ist_now.strftime("%Y%m%d_%H%M%S")
        
        async def handle_upload(file: UploadFile, file_type: str, replace: bool = False, seq=None):
            if replace:
                db.query(Attachment).filter(
                    Attachment.assessment_id == assessment.id,
                    Attachment.file_type == file_type
                ).delete()

            content = await file.read()
            destination_blob_name = build_blob_path(hospital_id, patient_session_id, file_type, file.filename, ist_now, seq=seq)
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

        for idx, dicom_file in enumerate(mammo_dicom, start=1):
            if dicom_file.filename:
                await handle_upload(dicom_file, "mammo_dicom", replace=False, seq=idx)

        if mammo_cc_left and mammo_cc_left.filename:
            await handle_upload(mammo_cc_left, "mammo_cc_left", replace=True)
        if mammo_cc_right and mammo_cc_right.filename:
            await handle_upload(mammo_cc_right, "mammo_cc_right", replace=True)
        if mammo_mlo_left and mammo_mlo_left.filename:
            await handle_upload(mammo_mlo_left, "mammo_mlo_left", replace=True)
        if mammo_mlo_right and mammo_mlo_right.filename:
            await handle_upload(mammo_mlo_right, "mammo_mlo_right", replace=True)

        if mammo_reading and mammo_reading.filename:
            await handle_upload(mammo_reading, "mammo_reading", replace=True)
        
        if us_video and us_video.filename:
            await handle_upload(us_video, "us_video", replace=True)
            
        if us_reading and us_reading.filename:
            await handle_upload(us_reading, "us_reading", replace=True)
            
        if biopsy_doc and biopsy_doc.filename:
            await handle_upload(biopsy_doc, "biopsy_reading", replace=True)

        if annot_cc_left and annot_cc_left.filename:
            await handle_upload(annot_cc_left, "annot_cc_left", replace=True)
        if annot_cc_right and annot_cc_right.filename:
            await handle_upload(annot_cc_right, "annot_cc_right", replace=True)
        if annot_mlo_left and annot_mlo_left.filename:
            await handle_upload(annot_mlo_left, "annot_mlo_left", replace=True)
        if annot_mlo_right and annot_mlo_right.filename:
            await handle_upload(annot_mlo_right, "annot_mlo_right", replace=True)

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
