"""
CRUD operations for database models.
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime, timezone

from app.models import (
    Customer, Call, Transcript, CallEvent, CallStatus, CallDirection,
    Appointment, AppointmentStatus, UrgencyLevel,
    ConversationStateModel, ConversationStatus, ConversationState,
    Service, Policy, FAQ, Record
)
from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Customer CRUD Operations
# ============================================================================

def get_customer_by_phone(db: Session, phone_number: str) -> Optional[Customer]:
    """Get customer by phone number."""
    return db.query(Customer).filter(Customer.phone_number == phone_number).first()


def get_customer_by_id(db: Session, customer_id: str) -> Optional[Customer]:
    """Get customer by ID."""
    return db.query(Customer).filter(Customer.id == customer_id).first()


def create_customer(
    db: Session,
    phone_number: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    **kwargs
) -> Customer:
    """Create a new customer."""
    customer = Customer(
        phone_number=phone_number,
        name=name,
        email=email,
        **kwargs
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    logger.info("customer_created", customer_id=customer.id, phone=phone_number)
    return customer


def update_customer(db: Session, customer_id: str, **kwargs) -> Optional[Customer]:
    """Update customer information."""
    customer = get_customer_by_id(db, customer_id)
    if customer:
        for key, value in kwargs.items():
            if hasattr(customer, key):
                setattr(customer, key, value)
        customer.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(customer)
        logger.info("customer_updated", customer_id=customer_id)
    return customer


def get_or_create_customer(db: Session, phone_number: str, **kwargs) -> Customer:
    """Get existing customer or create new one."""
    customer = get_customer_by_phone(db, phone_number)
    if not customer:
        customer = create_customer(db, phone_number, **kwargs)
    return customer


# ============================================================================
# Call CRUD Operations
# ============================================================================

def get_call_by_sid(db: Session, call_sid: str) -> Optional[Call]:
    """Get call by Call SID."""
    return db.query(Call).filter(Call.call_sid == call_sid).first()


def get_call_by_id(db: Session, call_id: str) -> Optional[Call]:
    """Get call by ID."""
    return db.query(Call).filter(Call.id == call_id).first()


def create_call(
    db: Session,
    call_sid: str,
    customer_id: str,
    from_number: str,
    to_number: str,
    direction: CallDirection,
    **kwargs
) -> Call:
    """Create a new call record and audit entry."""
    call = Call(
        call_sid=call_sid,
        customer_id=customer_id,
        from_number=from_number,
        to_number=to_number,
        direction=direction,
        **kwargs
    )
    db.add(call)
    db.commit()
    db.refresh(call)

    # Create audit record
    try:
        create_record(
            db,
            record_type="call",
            entity_id=str(call.id),
            entity_type="call",
            payload={
                "call_sid": call_sid,
                "customer_id": customer_id,
                "from_number": from_number,
                "to_number": to_number,
                "direction": direction.value if hasattr(direction, "value") else str(direction),
            },
            summary=f"Call from {from_number} to {to_number}",
        )
    except Exception as audit_exc:
        logger.warning("audit_record_creation_failed", call_id=call.id, error=str(audit_exc))

    logger.info("call_created", call_id=call.id, call_sid=call_sid)
    return call


def update_call(db: Session, call_id: str, **kwargs) -> Optional[Call]:
    """Update call information."""
    call = get_call_by_id(db, call_id)
    if call:
        for key, value in kwargs.items():
            if hasattr(call, key):
                setattr(call, key, value)
        call.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(call)
        logger.info("call_updated", call_id=call_id)
    return call


def update_call_by_sid(db: Session, call_sid: str, **kwargs) -> Optional[Call]:
    """Update call by Call SID."""
    call = get_call_by_sid(db, call_sid)
    if call:
        for key, value in kwargs.items():
            if hasattr(call, key):
                setattr(call, key, value)
        call.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(call)
        logger.info("call_updated", call_sid=call_sid)
    return call


def list_calls(db: Session, limit: int = 100) -> List[Call]:
    """List recent calls for API visibility."""
    return (
        db.query(Call)
        .order_by(desc(Call.created_at))
        .limit(limit)
        .all()
    )


def get_customer_calls(
    db: Session,
    customer_id: str,
    limit: int = 10
) -> List[Call]:
    """Get recent calls for a customer."""
    return (
        db.query(Call)
        .filter(Call.customer_id == customer_id)
        .order_by(desc(Call.created_at))
        .limit(limit)
        .all()
    )


# ============================================================================
# Transcript CRUD Operations
# ============================================================================

def create_transcript(
    db: Session,
    call_id: str,
    text: str,
    language: str = "en",
    **kwargs
) -> Transcript:
    """Create a new transcript and audit entry."""
    transcript = Transcript(
        call_id=call_id,
        text=text,
        language=language,
        **kwargs
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)

    # Create audit record
    try:
        create_record(
            db,
            record_type="transcript",
            entity_id=str(transcript.id),
            entity_type="transcript",
            payload={
                "call_id": call_id,
                "language": language,
                "text_preview": text[:200] + "..." if len(text) > 200 else text,
            },
            summary=f"Transcript for call {call_id} ({language})",
        )
    except Exception as audit_exc:
        logger.warning(
            "audit_record_creation_failed",
            transcript_id=transcript.id,
            call_id=call_id,
            error=str(audit_exc)
        )

    logger.info("transcript_created", transcript_id=transcript.id, call_id=call_id)
    return transcript


def get_transcript_by_call_id(db: Session, call_id: str) -> Optional[Transcript]:
    """Get transcript for a call."""
    return db.query(Transcript).filter(Transcript.call_id == call_id).first()


def list_transcripts(db: Session, limit: int = 100) -> List[Transcript]:
    """List recent transcripts for API visibility."""
    return (
        db.query(Transcript)
        .order_by(desc(Transcript.created_at))
        .limit(limit)
        .all()
    )


# ============================================================================
# CallEvent CRUD Operations
# ============================================================================

def create_call_event(
    db: Session,
    call_id: str,
    event_type: str,
    description: Optional[str] = None,
    event_data: Optional[dict] = None
) -> CallEvent:
    """Create a new call event and corresponding audit record."""
    event = CallEvent(
        call_id=call_id,
        event_type=event_type,
        description=description,
        event_data=event_data
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Create audit record for history tracking (records are never auto-deleted)
    try:
        create_record(
            db,
            record_type="event",
            entity_id=call_id,
            entity_type="call",
            payload={"event_type": event_type, "event_data": event_data},
            summary=description,
        )
    except Exception as audit_exc:
        logger.warning(
            "audit_record_creation_failed",
            event_id=event.id,
            call_id=call_id,
            error=str(audit_exc)
        )
        # Don't fail the event creation if audit record fails

    logger.info("call_event_created", event_id=event.id, call_id=call_id, event_type=event_type)
    return event


def get_call_events(db: Session, call_id: str) -> List[CallEvent]:
    """Get all events for a call."""
    return (
        db.query(CallEvent)
        .filter(CallEvent.call_id == call_id)
        .order_by(CallEvent.created_at)
        .all()
    )


# ============================================================================
# Appointment CRUD Operations
# ============================================================================

def _normalize_enum_str(value: str) -> str:
    """Normalize string to lowercase; PostgreSQL enums expect lowercase values."""
    return value.lower() if isinstance(value, str) else value


def create_appointment(
    db: Session,
    call_id: str,
    customer_id: str,
    **kwargs
) -> Appointment:
    """Create a new appointment and audit record."""
    # Normalize status/urgency to lowercase for PostgreSQL enum compatibility
    if "status" in kwargs and isinstance(kwargs["status"], str):
        kwargs["status"] = _normalize_enum_str(kwargs["status"])
    if "urgency" in kwargs and isinstance(kwargs["urgency"], str):
        kwargs["urgency"] = _normalize_enum_str(kwargs["urgency"])


    appointment = Appointment(
        call_id=call_id,
        customer_id=customer_id,
        **kwargs
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    # Create audit record for history tracking
    try:
        create_record(
            db,
            record_type="appointment",
            entity_id=str(appointment.id),
            entity_type="appointment",
            payload={
                "call_id": call_id,
                "customer_id": customer_id,
                "service_type": kwargs.get("service_type"),
                "urgency": kwargs.get("urgency"),
                "requested_date": str(kwargs.get("requested_date")) if kwargs.get("requested_date") else None,
            },
            summary=f"Appointment created for call {call_id}",
        )
    except Exception as audit_exc:
        logger.warning(
            "audit_record_creation_failed",
            appointment_id=appointment.id,
            call_id=call_id,
            error=str(audit_exc)
        )

    logger.info(
        "appointment_created",
        appointment_id=appointment.id,
        call_id=call_id
    )
    return appointment


def get_appointment_by_id(db: Session, appointment_id: str) -> Optional[Appointment]:
    """Get appointment by ID."""
    return db.query(Appointment).filter(Appointment.id == appointment_id).first()


def get_appointment_by_call_id(db: Session, call_id: str) -> Optional[Appointment]:
    """Get appointment by call ID."""
    return db.query(Appointment).filter(Appointment.call_id == call_id).first()


def get_customer_appointments(
    db: Session,
    customer_id: str,
    limit: int = 100
) -> List[Appointment]:
    """Get all appointments for a customer."""
    return (
        db.query(Appointment)
        .filter(Appointment.customer_id == customer_id)
        .order_by(desc(Appointment.created_at))
        .limit(limit)
        .all()
    )


def list_appointments(db: Session, limit: int = 100) -> List[Appointment]:
    """List recent appointments for API visibility."""
    return (
        db.query(Appointment)
        .order_by(desc(Appointment.created_at))
        .limit(limit)
        .all()
    )


def get_appointments_by_date_range(
    db: Session,
    start_date: datetime,
    end_date: datetime
) -> List[Appointment]:
    """Get all appointments within a date range."""
    return (
        db.query(Appointment)
        .filter(
            Appointment.scheduled_time_start >= start_date,
            Appointment.scheduled_time_start < end_date
        )
        .order_by(Appointment.scheduled_time_start)
        .all()
    )


def update_appointment(
    db: Session,
    appointment_id: str,
    **kwargs
) -> Optional[Appointment]:
    """Update appointment information."""
    # Normalize status/urgency to lowercase for PostgreSQL enum compatibility
    if "status" in kwargs and isinstance(kwargs["status"], str):
        kwargs["status"] = _normalize_enum_str(kwargs["status"])
    if "urgency" in kwargs and isinstance(kwargs["urgency"], str):
        kwargs["urgency"] = _normalize_enum_str(kwargs["urgency"])

    appointment = get_appointment_by_id(db, appointment_id)
    if appointment:
        for key, value in kwargs.items():
            if hasattr(appointment, key):
                setattr(appointment, key, value)
        db.commit()
        db.refresh(appointment)
        logger.info("appointment_updated", appointment_id=appointment_id)
    return appointment


def find_appointment_for_lookup(
    db: Session,
    appointment_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    scheduled_date: Optional[datetime] = None,
    statuses: Optional[List[str]] = None,
) -> Optional[Appointment]:
    """
    Locate an appointment using the best available identifier.

    Priority:
      1. ``appointment_id`` (exact match)
      2. ``customer_name`` + ``scheduled_date`` (fuzzy name, closest match)

    Only appointments whose status is in *statuses* are considered.
    Defaults to ``["scheduled", "confirmed", "pending"]``.
    """
    if statuses is None:
        statuses = ["scheduled", "confirmed", "pending"]

    # 1) Direct ID lookup
    if appointment_id:
        appt = get_appointment_by_id(db, appointment_id)
        if appt and (appt.status.value if hasattr(appt.status, "value") else appt.status) in statuses:
            return appt
        return None

    # 2) Name + optional date
    query = db.query(Appointment).filter(
        Appointment.status.in_(statuses)
    )
    if customer_name:
        query = query.filter(
            Appointment.contact_name.ilike(f"%{customer_name}%")
        )
    if scheduled_date:
        from datetime import timedelta
        day_start = scheduled_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        query = query.filter(
            Appointment.scheduled_time_start >= day_start,
            Appointment.scheduled_time_start < day_end,
        )

    # Return the closest upcoming appointment
    appt = (
        query.order_by(Appointment.scheduled_time_start.asc())
        .first()
    )
    return appt


# ============================================================================
# Conversation State CRUD Operations
# ============================================================================

def create_conversation_state(
    db: Session,
    call_id: str,
    customer_id: str,
    **kwargs
) -> ConversationStateModel:
    """Create a new conversation state."""
    # Normalize enum-like strings to lowercase for PostgreSQL
    for key in ("status", "current_state", "previous_state"):
        if key in kwargs and isinstance(kwargs[key], str):
            kwargs[key] = _normalize_enum_str(kwargs[key])

    conversation = ConversationStateModel(
        call_id=call_id,
        customer_id=customer_id,
        **kwargs
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    # Audit record for event log
    try:
        status_val = getattr(conversation.status, "value", str(conversation.status))
        state_val = getattr(
            conversation.current_state, "value", str(conversation.current_state)
        )
        create_record(
            db,
            record_type="conversation_state",
            entity_id=str(conversation.id),
            entity_type="conversation_state",
            payload={
                "call_id": call_id,
                "customer_id": customer_id,
                "status": status_val,
                "current_state": state_val,
            },
            summary=f"Conversation state created for call {call_id}",
        )
    except Exception as audit_exc:
        logger.warning(
            "audit_record_creation_failed",
            conversation_id=conversation.id,
            call_id=call_id,
            error=str(audit_exc)
        )

    logger.info(
        "conversation_state_created",
        conversation_id=conversation.id,
        call_id=call_id
    )
    return conversation


def get_conversation_state_by_id(
    db: Session,
    conversation_id: str
) -> Optional[ConversationStateModel]:
    """Get conversation state by ID."""
    return db.query(ConversationStateModel).filter(
        ConversationStateModel.id == conversation_id
    ).first()


def get_conversation_state_by_call_id(
    db: Session,
    call_id: str
) -> Optional[ConversationStateModel]:
    """Get conversation state by call ID."""
    return db.query(ConversationStateModel).filter(
        ConversationStateModel.call_id == call_id
    ).first()


def list_conversation_states(
    db: Session,
    limit: int = 100
) -> List[ConversationStateModel]:
    """List recent conversation states for API visibility."""
    return (
        db.query(ConversationStateModel)
        .order_by(desc(ConversationStateModel.updated_at))
        .limit(limit)
        .all()
    )


def get_active_conversations(
    db: Session,
    limit: int = 100
) -> List[ConversationStateModel]:
    """Get all active conversations."""
    return (
        db.query(ConversationStateModel)
        .filter(ConversationStateModel.status == ConversationStatus.ACTIVE)
        .order_by(desc(ConversationStateModel.last_interaction_at))
        .limit(limit)
        .all()
    )


def update_conversation_state(
    db: Session,
    conversation_id: str,
    **kwargs
) -> Optional[ConversationStateModel]:
    """Update conversation state."""
    for key in ("status", "current_state", "previous_state"):
        if key in kwargs and isinstance(kwargs[key], str):
            kwargs[key] = _normalize_enum_str(kwargs[key])

    conversation = get_conversation_state_by_id(db, conversation_id)
    if conversation:
        for key, value in kwargs.items():
            if hasattr(conversation, key):
                setattr(conversation, key, value)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(conversation)
        logger.info("conversation_state_updated", conversation_id=conversation_id)
    return conversation


# ============================================================================
# Service CRUD Operations
# ============================================================================

def get_service_by_key(db: Session, service_key: str) -> Optional[Service]:
    """Get service by key."""
    return db.query(Service).filter(Service.service_key == service_key).first()


def get_all_services(db: Session) -> List[Service]:
    """Get all services."""
    return db.query(Service).all()


def create_or_update_service(
    db: Session,
    service_key: str,
    name: str,
    description: str,
    price: str
) -> Service:
    """Create or update a service."""
    service = get_service_by_key(db, service_key)
    if service:
        service.name = name
        service.description = description
        service.price = price
        logger.info("service_updated", service_key=service_key)
    else:
        service = Service(
            service_key=service_key,
            name=name,
            description=description,
            price=price
        )
        db.add(service)
        logger.info("service_created", service_key=service_key)

    db.commit()
    db.refresh(service)
    return service


# ============================================================================
# Policy CRUD Operations
# ============================================================================

def get_policy_by_key(db: Session, policy_key: str) -> Optional[Policy]:
    """Get policy by key."""
    return db.query(Policy).filter(Policy.policy_key == policy_key).first()


def get_all_policies(db: Session) -> List[Policy]:
    """Get all policies."""
    return db.query(Policy).all()


def create_or_update_policy(
    db: Session,
    policy_key: str,
    name: str,
    content: str
) -> Policy:
    """Create or update a policy."""
    policy = get_policy_by_key(db, policy_key)
    if policy:
        policy.name = name
        policy.content = content
        logger.info("policy_updated", policy_key=policy_key)
    else:
        policy = Policy(
            policy_key=policy_key,
            name=name,
            content=content
        )
        db.add(policy)
        logger.info("policy_created", policy_key=policy_key)

    db.commit()
    db.refresh(policy)
    return policy


# ============================================================================
# FAQ CRUD Operations
# ============================================================================

def get_faq_by_question(db: Session, question: str) -> Optional[FAQ]:
    """Get FAQ by exact question match."""
    return db.query(FAQ).filter(FAQ.question == question).first()


def get_all_faqs(db: Session) -> List[FAQ]:
    """Get all FAQs."""
    return db.query(FAQ).all()


def search_faqs(db: Session, search_term: str, limit: int = 10) -> List[FAQ]:
    """Search FAQs by question or answer content."""
    search_pattern = f"%{search_term}%"
    return db.query(FAQ).filter(
        (FAQ.question.ilike(search_pattern)) | (FAQ.answer.ilike(search_pattern))
    ).limit(limit).all()


def create_or_update_faq(
    db: Session,
    question: str,
    answer: str
) -> FAQ:
    """Create or update an FAQ."""
    faq = get_faq_by_question(db, question)
    if faq:
        faq.answer = answer
        logger.info("faq_updated", question=question[:50])
    else:
        faq = FAQ(
            question=question,
            answer=answer
        )
        db.add(faq)
        logger.info("faq_created", question=question[:50])

    db.commit()
    db.refresh(faq)
    return faq


def get_service_by_id(db: Session, service_id: int) -> Optional[Service]:
    """Get service by primary key."""
    return db.query(Service).filter(Service.id == service_id).first()


def delete_service(db: Session, service_id: int) -> bool:
    """Delete a service by ID. Returns True if deleted."""
    service = get_service_by_id(db, service_id)
    if not service:
        return False
    db.delete(service)
    db.commit()
    logger.info("service_deleted", service_id=service_id)
    return True


def get_faq_by_id(db: Session, faq_id: int) -> Optional[FAQ]:
    """Get FAQ by primary key."""
    return db.query(FAQ).filter(FAQ.id == faq_id).first()


def delete_faq(db: Session, faq_id: int) -> bool:
    """Delete a FAQ by ID. Returns True if deleted."""
    faq = get_faq_by_id(db, faq_id)
    if not faq:
        return False
    db.delete(faq)
    db.commit()
    logger.info("faq_deleted", faq_id=faq_id)
    return True


# ============================================================================
# Record CRUD Operations (Audit / History Tracking)
# ============================================================================

def create_record(
    db: Session,
    record_type: str,
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    payload: Optional[dict] = None,
    summary: Optional[str] = None
) -> Record:
    """
    Create an audit record. Records are never automatically deleted.

    Args:
        record_type: Type of record (call, transcript, event, task, etc.)
        entity_id: ID of the source entity
        entity_type: Type of source entity
        payload: JSON payload with record-specific data
        summary: Human-readable summary

    Returns:
        Record: Created record
    """
    record = Record(
        record_type=record_type,
        entity_id=entity_id,
        entity_type=entity_type,
        payload=payload,
        summary=summary
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "record_created",
        record_id=record.id,
        record_type=record_type,
        entity_type=entity_type,
        entity_id=entity_id
    )
    return record


def get_records_by_entity(
    db: Session,
    entity_type: str,
    entity_id: str,
    limit: int = 100
) -> List[Record]:
    """Get records for a specific entity."""
    return (
        db.query(Record)
        .filter(
            Record.entity_type == entity_type,
            Record.entity_id == entity_id
        )
        .order_by(desc(Record.created_at))
        .limit(limit)
        .all()
    )


def get_records_by_type(
    db: Session,
    record_type: str,
    limit: int = 100
) -> List[Record]:
    """Get records by record type."""
    return (
        db.query(Record)
        .filter(Record.record_type == record_type)
        .order_by(desc(Record.created_at))
        .limit(limit)
        .all()
    )

