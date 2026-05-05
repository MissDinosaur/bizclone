"""
Celery tasks for background processing.
"""
from typing import Optional
from celery import Task
from celery.exceptions import Retry

from app.workers.celery_app import celery_app
from app.core.logging import get_logger
from app.core.exceptions import TranscriptionError
from app.services.voice import WhisperTranscriptionService
from app.services.ai import (
    IntentClassifier,
    EntityExtractor,
    ConversationManager,
    PriorityDetector,
    ResponseGenerator,
)
from app.services.scheduling import SchedulingService
from app.db.session import SessionLocal
from app.db.crud import (
    get_call_by_id,
    get_customer_by_id,
    create_transcript,
    update_call,
    update_call_by_sid,
    create_call_event,
    create_appointment,
    update_appointment,
    get_appointment_by_id,
    create_conversation_state,
    get_conversation_state_by_call_id,
    get_transcript_by_call_id,
    create_record,
)
from app.models import ConversationState, AppointmentStatus
from app.config.settings import settings

logger = get_logger(__name__)


class TranscriptionTask(Task):
    """Base task for transcription with retry logic."""

    autoretry_for = (TranscriptionError, Exception)
    retry_kwargs = {"max_retries": 3, "countdown": 5}
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max backoff
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=TranscriptionTask,
    name="app.workers.tasks.transcribe_audio_task"
)
def transcribe_audio_task(
    self,
    call_id: str,
    audio_file_path: str,
    language: Optional[str] = None
) -> dict:
    """
    Transcribe an audio file and store the result in the database.

    Args:
        call_id: UUID of the call
        audio_file_path: Path to the audio file
        language: Optional language code

    Returns:
        dict: Transcription result metadata
    """
    logger.info(
        "transcription_task_started",
        task_id=self.request.id,
        call_id=call_id,
        audio_file_path=audio_file_path,
        retry_count=self.request.retries
    )

    db = SessionLocal()

    try:
        # Get call from database
        call = get_call_by_id(db, call_id=call_id)
        if not call:
            logger.error("call_not_found", call_id=call_id)
            db.rollback()
            raise ValueError(f"Call not found: {call_id}")

        # Create transcription event
        create_call_event(
            db,
            call_id=call_id,
            event_type="transcription_started",
            description="Audio transcription started",
            event_data={
                "task_id": self.request.id,
                "audio_file_path": audio_file_path,
                "retry_count": self.request.retries
            }
        )

        # Initialize transcription service
        transcription_service = WhisperTranscriptionService()

        # Transcribe audio
        result = transcription_service.transcribe_file(
            audio_file_path=audio_file_path,
            language=language
        )

        # Store transcript in database
        transcript = create_transcript(
            db,
            call_id=call_id,
            text=result.text,
            language=result.language,
            confidence=result.confidence,
            model_used=result.model_name,
            processing_time_seconds=result.processing_time,
            audio_duration_seconds=result.duration,
            audio_file_path=audio_file_path
        )

        # Update call with transcript summary
        update_call_by_sid(
            db,
            call_sid=call.call_sid,
            summary=result.text[:500] if len(result.text) > 500 else result.text
        )

        # Create completion event
        create_call_event(
            db,
            call_id=call_id,
            event_type="transcription_completed",
            description="Audio transcription completed successfully",
            event_data={
                "task_id": self.request.id,
                "transcript_id": str(transcript.id),
                "text_length": len(result.text),
                "language": result.language,
                "confidence": result.confidence,
                "processing_time_seconds": result.processing_time
            }
        )

        logger.info(
            "transcription_task_completed",
            task_id=self.request.id,
            call_id=call_id,
            transcript_id=str(transcript.id),
            text_length=len(result.text),
            language=result.language,
            confidence=result.confidence
        )

        # Queue intent classification task
        try:
            classify_intent_task.delay(call_id, result.text)
            logger.info(
                "intent_classification_queued",
                call_id=call_id,
                task_id=self.request.id
            )
        except Exception as queue_exc:
            logger.warning(
                "intent_classification_queue_failed",
                call_id=call_id,
                error=str(queue_exc)
            )
            # Don't fail transcription if queuing fails

        # Create task audit record
        try:
            create_record(
                db,
                record_type="task",
                entity_id=call_id,
                entity_type="call",
                payload={
                    "task_name": "transcribe_audio",
                    "task_id": self.request.id,
                    "transcript_id": str(transcript.id),
                    "status": "success",
                    "processing_time_seconds": result.processing_time,
                },
                summary=f"Transcription completed for call {call_id}",
            )
        except Exception:
            pass

        return {
            "status": "success",
            "call_id": call_id,
            "transcript_id": str(transcript.id),
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "processing_time_seconds": result.processing_time
        }

    except ValueError as exc:
        logger.error(
            "transcription_task_failed_non_retryable",
            task_id=self.request.id,
            call_id=call_id,
            error=str(exc),
        )
        db.rollback()
        raise
    except Exception as exc:
        logger.error(
            "transcription_task_failed",
            task_id=self.request.id,
            call_id=call_id,
            audio_file_path=audio_file_path,
            retry_count=self.request.retries,
            error=str(exc),
            exc_info=True
        )
        db.rollback()

        # Create failure event
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="transcription_failed",
                description=f"Transcription failed: {str(exc)}",
                event_data={
                    "task_id": self.request.id,
                    "error": str(exc),
                    "retry_count": self.request.retries
                }
            )
        except Exception:
            db.rollback()

        raise self.retry(exc=exc)

    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.classify_intent")
def classify_intent_task(
    self,
    call_id: str,
    transcript_text: str
) -> dict:
    """
    Classify customer intent from transcript using GPT-4o-mini.

    Args:
        call_id: UUID of the call
        transcript_text: Transcribed text to classify

    Returns:
        dict: Classification result with intent and confidence
    """
    logger.info(
        "intent_classification_task_started",
        call_id=call_id,
        task_id=self.request.id,
        text_length=len(transcript_text)
    )

    db = SessionLocal()

    try:
        # Get call from database
        call = get_call_by_id(db, call_id)
        if not call:
            logger.error(
                "intent_classification_call_not_found",
                call_id=call_id
            )
            return {"error": "Call not found", "call_id": call_id}

        # Create event for classification started
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="intent_classification_started",
                event_data={"task_id": self.request.id}
            )
        except Exception:
            pass  # Don't fail if event creation fails

        # Initialize classifier
        classifier = IntentClassifier()

        # Classify intent
        result = classifier.classify(transcript_text)

        # Update call with intent and confidence
        update_call(
            db,
            call_id=call_id,
            intent=result.intent.value,
            intent_confidence=result.confidence
        )

        # Create event for classification completed
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="intent_classification_completed",
                event_data={
                    "task_id": self.request.id,
                    "intent": result.intent.value,
                    "confidence": result.confidence,
                    "reasoning": result.reasoning
                }
            )
        except Exception:
            pass  # Don't fail if event creation fails

        logger.info(
            "intent_classification_task_completed",
            call_id=call_id,
            task_id=self.request.id,
            intent=result.intent.value,
            confidence=result.confidence
        )

        # Queue entity extraction task
        try:
            extract_entities_task.delay(call_id, transcript_text)
            logger.info(
                "entity_extraction_queued",
                call_id=call_id,
                task_id=self.request.id
            )
        except Exception as queue_exc:
            logger.warning(
                "entity_extraction_queue_failed",
                call_id=call_id,
                error=str(queue_exc)
            )
            # Don't fail intent classification if queuing fails

        # Create task audit record
        try:
            create_record(
                db,
                record_type="task",
                entity_id=call_id,
                entity_type="call",
                payload={
                    "task_name": "classify_intent",
                    "task_id": self.request.id,
                    "intent": result.intent.value,
                    "confidence": result.confidence,
                    "status": "success",
                },
                summary=f"Intent classified as {result.intent.value} for call {call_id}",
            )
        except Exception:
            pass

        return {
            "call_id": call_id,
            "intent": result.intent.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning
        }

    except Exception as exc:
        logger.error(
            "intent_classification_task_failed",
            call_id=call_id,
            task_id=self.request.id,
            error=str(exc),
            exc_info=True
        )
        try:
            db.rollback()
        except Exception:
            pass

        # Create event for classification failed
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="intent_classification_failed",
                event_data={
                    "task_id": self.request.id,
                    "error": str(exc)
                }
            )
        except Exception:
            pass  # Don't fail if event creation fails

        return {
            "error": str(exc),
            "call_id": call_id
        }

    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.extract_entities")
def extract_entities_task(
    self,
    call_id: str,
    transcript_text: str
) -> dict:
    """
    Extract entities from transcript using GPT-4o-mini.

    Args:
        call_id: UUID of the call
        transcript_text: Transcribed text to extract entities from

    Returns:
        dict: Extraction result with entities
    """
    logger.info(
        "entity_extraction_task_started",
        call_id=call_id,
        task_id=self.request.id,
        text_length=len(transcript_text)
    )

    db = SessionLocal()

    try:
        # Get call from database
        call = get_call_by_id(db, call_id)
        if not call:
            logger.error(
                "entity_extraction_call_not_found",
                call_id=call_id
            )
            return {"error": "Call not found", "call_id": call_id}

        # Create event for extraction started
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="entity_extraction_started",
                event_data={"task_id": self.request.id}
            )
        except Exception:
            pass  # Don't fail if event creation fails

        # Initialize extractor
        extractor = EntityExtractor()

        # Extract entities
        result = extractor.extract(transcript_text)

        # ──────────────────────────────────────────────────────────
        # STRICT INTENT ROUTING — decide action BEFORE creating
        # any appointment record.  Cancel/reschedule must NEVER
        # create a new appointment.
        # ──────────────────────────────────────────────────────────
        from app.services.scheduling.intent_router import route_intent

        intent = call.intent  # may be None if classification failed
        entities_dict = {
            "requested_date": result.requested_date,
            "requested_time": getattr(result, "requested_time", None),
            "date_time_text": result.date_time_text,
            "service_type": result.service_type,
            "contact_name": result.contact_name,
            "contact_phone": result.contact_phone,
        }
        routing = route_intent(
            intent=intent or "",
            entities=entities_dict,
            transcript=transcript_text,
        )

        logger.info(
            "intent_routing_decision",
            call_id=call_id,
            intent=intent,
            action=routing.action,
            reason=routing.reason,
        )

        # ── CANCEL: route directly, do NOT create appointment ────
        if routing.action == "cancel":
            try:
                cancel_appointment_task.delay(
                    call_id=call_id,
                    customer_name=result.contact_name,
                    reason=result.notes or "Customer requested cancellation",
                )
                logger.info(
                    "cancel_task_routed",
                    call_id=call_id,
                )
            except Exception as q_exc:
                logger.warning(
                    "cancel_task_queue_failed",
                    call_id=call_id,
                    error=str(q_exc),
                )
            _log_extraction_event(
                db, call_id, self.request.id, result, routing
            )
            return {
                "call_id": call_id,
                "action": "cancel",
                "service_type": result.service_type,
            }

        # ── RESCHEDULE: route directly, do NOT create appointment ─
        if routing.action == "reschedule":
            new_start = result.requested_date
            if new_start is None:
                logger.warning(
                    "reschedule_missing_new_time",
                    call_id=call_id,
                )
            try:
                reschedule_appointment_task.delay(
                    call_id=call_id,
                    new_start_time=(
                        new_start.isoformat() if new_start else
                        ""
                    ),
                    customer_name=result.contact_name,
                    reason=result.notes or "Customer requested reschedule",
                )
                logger.info(
                    "reschedule_task_routed",
                    call_id=call_id,
                )
            except Exception as q_exc:
                logger.warning(
                    "reschedule_task_queue_failed",
                    call_id=call_id,
                    error=str(q_exc),
                )
            _log_extraction_event(
                db, call_id, self.request.id, result, routing
            )
            return {
                "call_id": call_id,
                "action": "reschedule",
                "service_type": result.service_type,
            }

        # ── INFO-ONLY intents (pricing, availability, etc.) ──────
        if routing.action == "info_only":
            _log_extraction_event(
                db, call_id, self.request.id, result, routing
            )
            logger.info(
                "info_only_intent_no_booking",
                call_id=call_id,
                intent=intent,
            )
            return {
                "call_id": call_id,
                "action": "info_only",
                "intent": intent,
                "service_type": result.service_type,
            }

        # ── BOOKING (action == "book" or "book_with_warning") ────
        # Only NOW do we create an appointment record.
        appointment = create_appointment(
            db,
            call_id=call_id,
            customer_id=call.customer_id,
            date_time_text=result.date_time_text,
            requested_date=result.requested_date,
            location_text=result.location_text,
            address=result.address,
            city=result.city,
            state=result.state,
            zip_code=result.zip_code,
            service_type=result.service_type,
            service_description=result.service_description,
            urgency=result.urgency or "medium",
            urgency_reason=result.urgency_reason,
            contact_phone=result.contact_phone,
            contact_email=result.contact_email,
            contact_name=result.contact_name,
            notes=result.notes,
        )

        # Create or update conversation state
        try:
            conversation = get_conversation_state_by_call_id(db, call_id)
            if not conversation:
                conversation = create_conversation_state(
                    db,
                    call_id=call_id,
                    customer_id=call.customer_id,
                    current_state=ConversationState.COLLECTING_INFO,
                    appointment_id=appointment.id,
                    context={
                        "extracted_entities": {
                            "service_type": result.service_type,
                            "urgency": result.urgency,
                            "has_date": result.requested_date is not None,
                            "has_location": result.address is not None,
                        }
                    },
                )
            else:
                manager = ConversationManager(db)
                manager.update_context(
                    conversation,
                    {
                        "appointment_id": appointment.id,
                        "extracted_entities": {
                            "service_type": result.service_type,
                            "urgency": result.urgency,
                            "has_date": result.requested_date is not None,
                            "has_location": result.address is not None,
                        },
                    },
                )
        except Exception as conv_exc:
            logger.warning(
                "conversation_state_update_failed",
                call_id=call_id,
                error=str(conv_exc),
            )

        # Log extraction event
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="entity_extraction_completed",
                event_data={
                    "task_id": self.request.id,
                    "appointment_id": appointment.id,
                    "service_type": result.service_type,
                    "urgency": result.urgency,
                    "routing_action": routing.action,
                },
            )
        except Exception:
            pass

        logger.info(
            "entity_extraction_task_completed",
            call_id=call_id,
            task_id=self.request.id,
            appointment_id=appointment.id,
            service_type=result.service_type,
            urgency=result.urgency,
            routing_action=routing.action,
        )

        # Queue scheduling task — ONLY for booking intents
        try:
            schedule_appointment_task.delay(
                call_id,
                str(appointment.id),
                intent or "booking",
            )
            logger.info(
                "scheduling_task_queued",
                call_id=call_id,
                appointment_id=appointment.id,
                intent=intent,
                task_id=self.request.id,
            )
        except Exception as queue_exc:
            logger.warning(
                "scheduling_task_queue_failed",
                call_id=call_id,
                appointment_id=appointment.id,
                error=str(queue_exc),
            )

        # Create task audit record
        try:
            create_record(
                db,
                record_type="task",
                entity_id=call_id,
                entity_type="call",
                payload={
                    "task_name": "extract_entities",
                    "task_id": self.request.id,
                    "appointment_id": str(appointment.id),
                    "service_type": result.service_type,
                    "urgency": result.urgency,
                    "routing_action": routing.action,
                    "status": "success",
                },
                summary=f"Entities extracted for call {call_id}",
            )
        except Exception:
            pass

        return {
            "call_id": call_id,
            "appointment_id": appointment.id,
            "action": routing.action,
            "service_type": result.service_type,
            "urgency": result.urgency,
            "has_date": result.requested_date is not None,
            "has_location": result.address is not None,
        }

    except Exception as exc:
        logger.error(
            "entity_extraction_task_failed",
            call_id=call_id,
            task_id=self.request.id,
            error=str(exc),
            exc_info=True
        )
        try:
            db.rollback()
        except Exception:
            pass

        # Create event for extraction failed
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="entity_extraction_failed",
                event_data={
                    "task_id": self.request.id,
                    "error": str(exc)
                }
            )
        except Exception:
            pass  # Don't fail if event creation fails

        return {
            "error": str(exc),
            "call_id": call_id
        }

    finally:
        db.close()


# ------------------------------------------------------------------
# Helper: log extraction event for non-booking intents
# ------------------------------------------------------------------

def _log_extraction_event(db, call_id, task_id, result, routing):
    """Log an extraction event for cancel/reschedule/info_only intents."""
    try:
        create_call_event(
            db,
            call_id=call_id,
            event_type="entity_extraction_completed",
            event_data={
                "task_id": task_id,
                "service_type": result.service_type,
                "urgency": result.urgency,
                "routing_action": routing.action,
                "routing_reason": routing.reason,
            },
        )
    except Exception:
        pass
    try:
        create_record(
            db,
            record_type="task",
            entity_id=call_id,
            entity_type="call",
            payload={
                "task_name": "extract_entities",
                "task_id": task_id,
                "routing_action": routing.action,
                "service_type": result.service_type,
                "status": "success",
            },
            summary=f"Entities extracted (action={routing.action}) for call {call_id}",
        )
    except Exception:
        pass


@celery_app.task(name="detect_priority", bind=True)
def detect_priority_task(self, call_id: str) -> dict:
    """
    Detect priority level and emergency status from transcript.

    Args:
        call_id: UUID of the call

    Returns:
        dict: Priority detection result
    """
    db = SessionLocal()

    try:
        # Get call
        call = get_call_by_id(db, call_id)
        if not call:
            logger.error("priority_detection_call_not_found", call_id=call_id)
            return {"error": "Call not found", "call_id": call_id}

        # Get transcript (Call has transcripts plural; use latest)
        transcript = get_transcript_by_call_id(db, call_id)
        if not transcript or not transcript.text:
            logger.warning(
                "priority_detection_no_transcript",
                call_id=call_id
            )
            return {
                "call_id": call_id,
                "skipped": True,
                "reason": "No transcript available"
            }

        transcript_text = transcript.text

        # Initialize detector
        detector = PriorityDetector()

        # Detect priority
        result = detector.detect(
            transcript_text,
            intent=call.intent
        )

        # Update call with emergency flag
        if result.is_emergency:
            update_call(
                db,
                str(call.id),
                is_emergency="yes"
            )

        # Update appointment urgency if exists
        if call.appointments:
            appointment = call.appointments[0]
            update_appointment(
                db,
                appointment.id,
                urgency=result.urgency_level,
                urgency_reason=result.reason
            )

        # Update conversation state if emergency
        if result.is_emergency:
            conversation = get_conversation_state_by_call_id(db, call_id)
            if conversation:
                manager = ConversationManager(db)
                manager.mark_emergency(conversation)

        # Create event for priority detection
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="priority_detected",
                event_data={
                    "task_id": self.request.id,
                    "is_emergency": result.is_emergency,
                    "urgency_level": result.urgency_level,
                    "confidence": result.confidence,
                    "detected_keywords": result.detected_keywords,
                    "reason": result.reason,
                    "should_escalate": detector.should_escalate(result)
                }
            )
        except Exception:
            pass  # Don't fail if event creation fails

        logger.info(
            "priority_detection_task_completed",
            call_id=call_id,
            task_id=self.request.id,
            is_emergency=result.is_emergency,
            urgency_level=result.urgency_level,
            confidence=result.confidence
        )

        # Create task audit record
        try:
            create_record(
                db,
                record_type="task",
                entity_id=call_id,
                entity_type="call",
                payload={
                    "task_name": "detect_priority",
                    "task_id": self.request.id,
                    "is_emergency": result.is_emergency,
                    "urgency_level": result.urgency_level,
                    "status": "success",
                },
                summary=f"Priority detected for call {call_id} (emergency={result.is_emergency})",
            )
        except Exception:
            pass

        return {
            "call_id": call_id,
            "is_emergency": result.is_emergency,
            "urgency_level": result.urgency_level,
            "confidence": result.confidence,
            "detected_keywords": result.detected_keywords,
            "reason": result.reason,
            "should_escalate": detector.should_escalate(result)
        }

    except Exception as exc:
        logger.error(
            "priority_detection_task_failed",
            call_id=call_id,
            task_id=self.request.id,
            error=str(exc),
            exc_info=True
        )
        try:
            db.rollback()
        except Exception:
            pass

        # Create event for detection failed
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="priority_detection_failed",
                event_data={
                    "task_id": self.request.id,
                    "error": str(exc)
                }
            )
        except Exception:
            pass  # Don't fail if event creation fails

        return {
            "error": str(exc),
            "call_id": call_id
        }

    finally:
        db.close()


@celery_app.task(name="schedule_appointment", bind=True)
def schedule_appointment_task(
    self,
    call_id: str,
    appointment_id: str,
    intent: str
) -> dict:
    """
    Schedule an appointment using the SchedulingService.

    This task is called after entity extraction to find and assign
    a specific time slot for the appointment.

    Args:
        call_id: UUID of the call
        appointment_id: UUID of the appointment
        intent: Customer intent (booking, emergency, etc.)

    Returns:
        dict: Scheduling result
    """
    logger.info(
        "schedule_appointment_task_started",
        call_id=call_id,
        appointment_id=appointment_id,
        intent=intent,
        task_id=self.request.id
    )

    db = SessionLocal()

    try:
        # Get appointment
        appointment = get_appointment_by_id(db, appointment_id)
        if not appointment:
            logger.error(
                "schedule_appointment_not_found",
                appointment_id=appointment_id
            )
            return {"error": "Appointment not found", "appointment_id": appointment_id}

        # Initialize scheduling service
        scheduler = SchedulingService()

        # Determine if this is an emergency
        urgency_val = getattr(appointment.urgency, "value", str(appointment.urgency or ""))
        is_emergency = (
            intent == "emergency" or
            urgency_val == "emergency"
        )

        # Schedule the appointment (scheduler mutates appointment in place)
        result = scheduler.schedule_appointment(
            db,
            appointment,
            requested_time=appointment.requested_date,
            force_emergency=is_emergency
        )

        if result.success:
            # Update appointment with scheduled time (from mutated appointment)
            update_appointment(
                db,
                appointment_id=appointment_id,
                scheduled_time_start=appointment.scheduled_time_start,
                scheduled_time_end=appointment.scheduled_time_end,
                status=AppointmentStatus.SCHEDULED.value
            )

            # Create event
            create_call_event(
                db,
                call_id=call_id,
                event_type="appointment_scheduled",
                event_data={
                    "task_id": self.request.id,
                    "appointment_id": appointment_id,
                    "scheduled_time": result.scheduled_time.isoformat(),
                    "is_emergency": is_emergency
                }
            )

            logger.info(
                "schedule_appointment_task_completed",
                call_id=call_id,
                appointment_id=appointment_id,
                scheduled_time=result.scheduled_time.isoformat(),
                task_id=self.request.id
            )

            # ----------------------------------------------------------
            # Google Calendar: conflict-free event creation
            # ----------------------------------------------------------
            try:
                from app.services.integrations.google_calendar import (
                    create_calendar_event as create_gcal_event,
                    has_conflict as gcal_has_conflict,
                    find_next_available_slot as gcal_find_slot,
                    _get_target_calendar_id,
                )

                duration = getattr(
                    settings, "appointment_duration_minutes", 60
                )
                cal_id = _get_target_calendar_id()
                original_start = result.scheduled_time
                final_start = original_start

                # --- Conflict detection & auto-reschedule ---
                if gcal_has_conflict(
                    final_start, duration, calendar_id=cal_id
                ):
                    logger.info(
                        "google_calendar_conflict_detected",
                        calendar_id=cal_id,
                        original_start=final_start.isoformat(),
                        appointment_id=appointment_id,
                    )
                    new_slot = gcal_find_slot(
                        preferred_start=final_start,
                        duration_minutes=duration,
                        calendar_id=cal_id,
                    )
                    if new_slot is not None:
                        final_start = new_slot
                        from datetime import timedelta as _td
                        update_appointment(
                            db,
                            appointment_id=appointment_id,
                            scheduled_time_start=final_start,
                            scheduled_time_end=(
                                final_start
                                + _td(minutes=duration)
                            ),
                        )
                        logger.info(
                            "appointment_rescheduled",
                            appointment_id=appointment_id,
                            calendar_id=cal_id,
                            original=original_start.isoformat(),
                            new_start=final_start.isoformat(),
                        )
                    else:
                        logger.warning(
                            "google_calendar_no_available_slot",
                            calendar_id=cal_id,
                            appointment_id=appointment_id,
                        )

                # --- Build rich summary & description ---
                service_label = (
                    (appointment.service_type or "Appointment")
                    .replace("_", " ").title()
                )
                customer = get_customer_by_id(
                    db, appointment.customer_id
                )
                customer_name = (
                    appointment.contact_name
                    or (
                        customer.name if customer else None
                    )
                    or "Customer"
                )
                summary = f"{service_label} – {customer_name}"

                desc_parts = []
                if appointment.contact_phone:
                    desc_parts.append(
                        f"Customer Phone: "
                        f"{appointment.contact_phone}"
                    )
                biz_phone = getattr(
                    settings, "business_phone", ""
                )
                if biz_phone:
                    desc_parts.append(
                        f"Business Phone: {biz_phone}"
                    )
                if appointment.notes:
                    desc_parts.append(
                        f"Notes: {appointment.notes}"
                    )
                if appointment.service_description:
                    desc_parts.append(
                        f"Service: "
                        f"{appointment.service_description}"
                    )
                desc_parts.append(
                    f"Appointment ID: {appointment_id}"
                )
                desc_parts.append(f"Call ID: {call_id}")
                description = "\n".join(desc_parts)

                # --- Create the event ---
                from datetime import timedelta as _td2
                end_start = (
                    final_start + _td2(minutes=duration)
                )
                event_id = create_gcal_event(
                    summary=summary,
                    start_time=final_start,
                    duration_minutes=duration,
                    calendar_id=cal_id,
                    description=description,
                )
                if event_id:
                    # Persist event ID on appointment
                    update_appointment(
                        db,
                        appointment_id=appointment_id,
                        google_event_id=event_id,
                    )
                    logger.info(
                        "google_calendar_event_success",
                        event_id=event_id,
                        calendar_id=cal_id,
                        appointment_id=appointment_id,
                        final_start=final_start.isoformat(),
                        final_end=end_start.isoformat(),
                    )
                else:
                    logger.warning(
                        "google_calendar_event_returned_none",
                        calendar_id=cal_id,
                        appointment_id=appointment_id,
                    )
            except Exception as gcal_exc:
                logger.warning(
                    "google_calendar_event_skipped",
                    call_id=call_id,
                    appointment_id=appointment_id,
                    error=str(gcal_exc),
                )

            # Create task audit record
            try:
                create_record(
                    db,
                    record_type="task",
                    entity_id=call_id,
                    entity_type="call",
                    payload={
                        "task_name": "schedule_appointment",
                        "task_id": self.request.id,
                        "appointment_id": appointment_id,
                        "scheduled_time": result.scheduled_time.isoformat(),
                        "status": "success",
                    },
                    summary=f"Appointment {appointment_id} scheduled for call {call_id}",
                )
            except Exception:
                pass

            return {
                "success": True,
                "call_id": call_id,
                "appointment_id": appointment_id,
                "scheduled_time": result.scheduled_time.isoformat(),
                "message": result.message
            }
        else:
            # Scheduling failed - mark as pending
            update_appointment(
                db,
                appointment_id=appointment_id,
                status=AppointmentStatus.PENDING.value
            )

            # Create event
            create_call_event(
                db,
                call_id=call_id,
                event_type="appointment_scheduling_failed",
                event_data={
                    "task_id": self.request.id,
                    "appointment_id": appointment_id,
                    "reason": result.message
                }
            )

            logger.warning(
                "schedule_appointment_task_failed_no_slots",
                call_id=call_id,
                appointment_id=appointment_id,
                reason=result.message,
                task_id=self.request.id
            )

            return {
                "success": False,
                "call_id": call_id,
                "appointment_id": appointment_id,
                "message": result.message
            }

    except Exception as exc:
        logger.error(
            "schedule_appointment_task_error",
            call_id=call_id,
            appointment_id=appointment_id,
            task_id=self.request.id,
            error=str(exc),
            exc_info=True
        )
        try:
            db.rollback()
        except Exception:
            pass

        # Create event for scheduling error
        try:
            create_call_event(
                db,
                call_id=call_id,
                event_type="appointment_scheduling_error",
                event_data={
                    "task_id": self.request.id,
                    "appointment_id": appointment_id,
                    "error": str(exc)
                }
            )
        except Exception:
            pass

        return {
            "error": str(exc),
            "call_id": call_id,
            "appointment_id": appointment_id
        }

    finally:
        db.close()



# ====================================================================
# Cancel / Reschedule Celery Tasks
# ====================================================================


@celery_app.task(bind=True, name="cancel_appointment")
def cancel_appointment_task(
    self,
    call_id: str,
    appointment_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    reason: Optional[str] = None,
):
    """
    Celery task: cancel an appointment.

    Can be triggered from the pipeline when intent == ``cancel``.
    """
    from app.services.scheduling.cancel import CancellationService
    from datetime import datetime as _dt

    logger.info(
        "cancel_appointment_task_started",
        call_id=call_id,
        appointment_id=appointment_id,
        customer_name=customer_name,
        task_id=self.request.id,
    )

    db = SessionLocal()
    try:
        svc = CancellationService()
        parsed_date = None
        if scheduled_date:
            try:
                parsed_date = _dt.fromisoformat(scheduled_date)
            except ValueError:
                pass

        result = svc.cancel(
            db,
            appointment_id=appointment_id,
            customer_name=customer_name,
            scheduled_date=parsed_date,
            reason=reason,
            call_id=call_id,
        )

        logger.info(
            "cancel_appointment_task_completed",
            success=result.success,
            appointment_id=result.appointment_id,
            message=result.message,
        )
        return {
            "success": result.success,
            "appointment_id": result.appointment_id,
            "message": result.message,
        }
    except Exception as exc:
        logger.error(
            "cancel_appointment_task_error",
            call_id=call_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return {"error": str(exc), "call_id": call_id}
    finally:
        db.close()


@celery_app.task(bind=True, name="reschedule_appointment")
def reschedule_appointment_task(
    self,
    call_id: str,
    new_start_time: str,
    appointment_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    scheduled_date: Optional[str] = None,
    new_end_time: Optional[str] = None,
    reason: Optional[str] = None,
):
    """
    Celery task: reschedule an appointment.

    Can be triggered from the pipeline when intent == ``reschedule``.
    """
    from app.services.scheduling.reschedule import RescheduleService
    from datetime import datetime as _dt

    logger.info(
        "reschedule_appointment_task_started",
        call_id=call_id,
        appointment_id=appointment_id,
        new_start_time=new_start_time,
        task_id=self.request.id,
    )

    db = SessionLocal()
    try:
        svc = RescheduleService()
        parsed_start = _dt.fromisoformat(new_start_time)
        parsed_end = (
            _dt.fromisoformat(new_end_time)
            if new_end_time else None
        )
        parsed_date = None
        if scheduled_date:
            try:
                parsed_date = _dt.fromisoformat(scheduled_date)
            except ValueError:
                pass

        result = svc.reschedule(
            db,
            new_start_time=parsed_start,
            appointment_id=appointment_id,
            customer_name=customer_name,
            scheduled_date=parsed_date,
            new_end_time=parsed_end,
            reason=reason,
            call_id=call_id,
        )

        logger.info(
            "reschedule_appointment_task_completed",
            success=result.success,
            appointment_id=result.appointment_id,
            message=result.message,
        )
        return {
            "success": result.success,
            "appointment_id": result.appointment_id,
            "new_start": (
                result.new_start.isoformat()
                if result.new_start else None
            ),
            "new_end": (
                result.new_end.isoformat()
                if result.new_end else None
            ),
            "message": result.message,
        }
    except Exception as exc:
        logger.error(
            "reschedule_appointment_task_error",
            call_id=call_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return {"error": str(exc), "call_id": call_id}
    finally:
        db.close()
