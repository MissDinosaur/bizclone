"""
Appointment model for storing extracted appointment information.
"""
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid

from app.db.base import Base


def generate_uuid():
    """Generate a UUID string."""
    return str(uuid.uuid4())


class AppointmentStatus(str, enum.Enum):
    """Appointment status enumeration."""
    PENDING = "pending"  # Extracted but not confirmed
    CONFIRMED = "confirmed"  # Customer confirmed
    SCHEDULED = "scheduled"  # Scheduled in calendar
    COMPLETED = "completed"  # Service completed
    CANCELED = "canceled"  # Appointment canceled
    NO_SHOW = "no_show"  # Customer didn't show up


class UrgencyLevel(str, enum.Enum):
    """Urgency level enumeration."""
    LOW = "low"  # Can wait days/weeks
    MEDIUM = "medium"  # Within a few days
    HIGH = "high"  # Within 24 hours
    URGENT = "urgent"  # Same day
    EMERGENCY = "emergency"  # Immediate (flooding, burst pipe, etc.)


class Appointment(Base):
    """Appointment model for storing extracted appointment data."""
    
    __tablename__ = "appointments"
    
    # Primary Key
    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    
    # Foreign Keys
    call_id = Column(
        String,
        ForeignKey("calls.id"),
        nullable=False,
        index=True
    )
    customer_id = Column(
        String,
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )
    
    # Appointment Details
    # values_callable ensures PostgreSQL receives enum values ('pending') not names ('PENDING')
    status = Column(
        SQLEnum(
            AppointmentStatus,
            values_callable=lambda obj: [e.value for e in obj],
            name="appointmentstatus",
            create_constraint=False,
            create_type=False,
        ),
        default=AppointmentStatus.PENDING,
        nullable=False
    )
    
    # Extracted Date/Time Information
    requested_date = Column(DateTime(timezone=True), nullable=True)
    requested_time_start = Column(DateTime(timezone=True), nullable=True)
    requested_time_end = Column(DateTime(timezone=True), nullable=True)
    date_time_text = Column(Text, nullable=True)  # Original text: "tomorrow at 2pm"
    
    # Scheduled Date/Time (confirmed)
    scheduled_date = Column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_time_start = Column(DateTime(timezone=True), nullable=True)
    scheduled_time_end = Column(DateTime(timezone=True), nullable=True)
    
    # Location Information
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    location_text = Column(Text, nullable=True)  # Original text: "my house on Main St"
    
    # Service Information
    service_type = Column(String, nullable=True)  # e.g., "sink_repair", "drain_cleaning"
    service_description = Column(Text, nullable=True)  # "fix my leaking sink"
    
    # Urgency
    # values_callable ensures PostgreSQL receives enum values ('medium') not names ('MEDIUM')
    urgency = Column(
        SQLEnum(
            UrgencyLevel,
            values_callable=lambda obj: [e.value for e in obj],
            name="urgencylevel",
            create_constraint=False,
            create_type=False,
        ),
        default=UrgencyLevel.MEDIUM,
        nullable=False
    )
    urgency_reason = Column(Text, nullable=True)  # "water everywhere", "can wait"
    
    # Contact Information
    contact_phone = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    
    # Google Calendar
    google_event_id = Column(String, nullable=True, index=True)

    # Additional Notes
    notes = Column(Text, nullable=True)
    
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
    
    # Relationships
    call = relationship("Call", back_populates="appointments", lazy="select")
    customer = relationship("Customer", back_populates="appointments", lazy="select")
    conversation_state = relationship("ConversationStateModel", back_populates="appointment", uselist=False, lazy="select")
    
    def __repr__(self):
        return (
            f"<Appointment(id={self.id}, "
            f"status={self.status}, "
            f"urgency={self.urgency})>"
        )

