"""
Call model for storing call information.
"""
from sqlalchemy import (
    Column, String, DateTime, Integer, Float,
    ForeignKey, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid

from app.db.base import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class CallStatus(str, enum.Enum):
    """Call status enumeration."""
    INITIATED = "initiated"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no-answer"
    CANCELED = "canceled"


class CallDirection(str, enum.Enum):
    """Call direction enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Call(Base):
    """Call model."""
    
    __tablename__ = "calls"
    
    # Primary Key
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    
    # Call Identification
    call_sid = Column(String, unique=True, nullable=False, index=True)
    
    # Customer Reference
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False, index=True)
    
    # Call Details
    from_number = Column(String, nullable=False)
    to_number = Column(String, nullable=False)
    direction = Column(SQLEnum(CallDirection), nullable=False)
    status = Column(SQLEnum(CallStatus), default=CallStatus.INITIATED, nullable=False)
    
    # Call Metadata
    duration_seconds = Column(Integer, nullable=True)
    recording_url = Column(String, nullable=True)
    recording_sid = Column(String, nullable=True)
    recording_duration = Column(Integer, nullable=True)
    
    # Location Information
    from_city = Column(String, nullable=True)
    from_state = Column(String, nullable=True)
    from_country = Column(String, nullable=True)
    
    # AI Processing
    summary = Column(Text, nullable=True)
    intent = Column(String, nullable=True)  # e.g., "booking", "emergency", "pricing"
    intent_confidence = Column(Float, nullable=True)  # Confidence score 0.0-1.0
    sentiment = Column(String, nullable=True)  # e.g., "positive", "negative", "neutral"
    is_emergency = Column(SQLEnum("yes", "no", name="emergency_enum"), default="no", nullable=False)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="calls", lazy="select")
    transcripts = relationship("Transcript", back_populates="call", cascade="all, delete-orphan", lazy="select")
    events = relationship("CallEvent", back_populates="call", cascade="all, delete-orphan", lazy="select")
    appointments = relationship("Appointment", back_populates="call", cascade="all, delete-orphan", lazy="select")
    conversation_state = relationship("ConversationStateModel", back_populates="call", uselist=False, lazy="select")
    
    def __repr__(self):
        return f"<Call(id={self.id}, call_sid={self.call_sid}, status={self.status})>"

