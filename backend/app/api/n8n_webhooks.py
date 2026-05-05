"""
n8n webhook endpoints for handling simulated voice calls.
This is used for local testing and development.
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
import uuid

from app.core.logging import get_logger, log_call_event
from app.core.exceptions import ValidationError
from app.config.settings import settings
from app.db import get_db
from app.db.crud import (
    get_or_create_customer,
    create_call,
    update_call_by_sid,
    create_call_event,
    get_call_by_sid,
)
from app.models import CallDirection
from app.models.call import CallStatus as CallStatusEnum
from app.services.voice import AudioHandler
from app.workers.tasks import transcribe_audio_task

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks/n8n", tags=["n8n Webhooks"])

# Initialize audio handler
audio_handler = AudioHandler()


@router.post(
    "/voice/upload",
    status_code=status.HTTP_200_OK,
    summary="Upload Voice Recording",
    description="Upload a voice recording for processing (simulated call)"
)
async def upload_voice_recording(
    audio_file: UploadFile = File(..., description="Audio file (WAV, MP3, etc.)"),
    from_number: str = Form(..., description="Caller's phone number"),
    to_number: Optional[str] = Form(None, description="Called number"),
    customer_name: Optional[str] = Form(None, description="Customer name"),
    call_sid: Optional[str] = Form(None, description="Optional call session ID"),
    db: Session = Depends(get_db),
):
    """
    Upload a voice recording for processing.
    
    This endpoint simulates an inbound call by accepting an audio file upload.
    It's designed for use with n8n workflows for local testing.
    
    Args:
        audio_file: Audio file to process
        from_number: Caller's phone number
        to_number: Called number (defaults to business phone)
        customer_name: Optional customer name
        call_sid: Optional call session ID (auto-generated if not provided)
        db: Database session
    
    Returns:
        dict: Call information including call_sid and status
    """
    try:
        # Generate call SID if not provided
        if not call_sid:
            call_sid = f"n8n_{uuid.uuid4().hex[:24]}"
        
        # Use business phone as default 'to' number
        if not to_number:
            to_number = settings.business_phone
        
        logger.info(
            "n8n_voice_upload_received",
            call_sid=call_sid,
            from_number=from_number,
            filename=audio_file.filename,
            content_type=audio_file.content_type
        )
        
        # Read audio file content
        audio_content = await audio_file.read()
        
        # Save recording to local storage
        try:
            audio_metadata = await audio_handler.save_recording(
                call_sid=call_sid,
                content=audio_content,
                content_type=audio_file.content_type,
                filename=None  # Auto-generate filename
            )
        except ValidationError as exc:
            logger.error(
                "audio_validation_failed",
                call_sid=call_sid,
                error=str(exc)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc)
            )
        
        # Get or create customer
        customer = get_or_create_customer(
            db,
            phone_number=from_number,
            name=customer_name,
        )
        
        # Create call record
        call = create_call(
            db,
            call_sid=call_sid,
            customer_id=customer.id,
            from_number=from_number,
            to_number=to_number,
            direction=CallDirection.INBOUND,
            status=CallStatusEnum.COMPLETED,  # n8n uploads are already completed
            recording_url=audio_metadata.file_path,  # Store local file path
            recording_duration=None,  # Will be populated by transcription
        )
        
        # Create call event
        create_call_event(
            db,
            call_id=call.id,
            event_type="recording_uploaded",
            description=f"Voice recording uploaded via n8n from {from_number}",
            event_data={
                "filename": audio_file.filename,
                "file_size": audio_metadata.file_size,
                "file_path": audio_metadata.file_path,
                "content_type": audio_file.content_type,
            }
        )
        
        log_call_event(
            logger,
            "n8n_recording_saved",
            call_sid,
            customer_id=str(customer.id),
            call_id=str(call.id),
            file_path=audio_metadata.file_path,
            file_size=audio_metadata.file_size
        )

        # Queue transcription task
        try:
            task = transcribe_audio_task.delay(
                call_id=str(call.id),
                audio_file_path=audio_metadata.file_path
            )

            logger.info(
                "transcription_task_queued",
                call_sid=call_sid,
                call_id=str(call.id),
                task_id=task.id
            )

            # Create event for task queued
            create_call_event(
                db,
                call_id=call.id,
                event_type="transcription_queued",
                description="Transcription task queued for processing",
                event_data={
                    "task_id": task.id,
                    "audio_file_path": audio_metadata.file_path
                }
            )
        except Exception as queue_exc:
            logger.error(
                "transcription_queue_failed",
                call_sid=call_sid,
                call_id=str(call.id),
                error=str(queue_exc),
                exc_info=True
            )
            # Don't fail the upload if queuing fails

        return {
            "status": "success",
            "call_sid": call_sid,
            "call_id": str(call.id),
            "customer_id": str(customer.id),
            "recording_path": audio_metadata.file_path,
            "file_size": audio_metadata.file_size,
            "message": "Recording uploaded successfully and queued for processing"
        }
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "n8n_upload_error",
            call_sid=call_sid if 'call_sid' in locals() else None,
            from_number=from_number,
            error=str(exc),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process recording: {str(exc)}"
        )


@router.get(
    "/call/{call_sid}",
    status_code=status.HTTP_200_OK,
    summary="Get Call Information",
    description="Retrieve information about a call by call SID"
)
async def get_call_info(
    call_sid: str,
    db: Session = Depends(get_db),
):
    """
    Get call information by call SID.

    Args:
        call_sid: Call session ID
        db: Database session

    Returns:
        dict: Call information
    """
    call = get_call_by_sid(db, call_sid=call_sid)

    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call not found: {call_sid}"
        )

    return {
        "call_sid": call.call_sid,
        "call_id": str(call.id),
        "customer_id": str(call.customer_id),
        "from_number": call.from_number,
        "to_number": call.to_number,
        "status": call.status,
        "direction": call.direction,
        "recording_url": call.recording_url,
        "recording_duration": call.recording_duration,
        "created_at": call.created_at.isoformat() if call.created_at else None,
    }
