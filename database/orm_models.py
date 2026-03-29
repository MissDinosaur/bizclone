"""
Database models for BizClone application using SQLAlchemy.

Defines all persistent data models:
1. EmailHistory - Customer email conversations
2. Booking - Appointment reservations
3. KnowledgeBase - Knowledge base versions with tracking
4. KBFeedback - Knowledge base update log
5. ConversationState - Lightweight per-conversation state for messaging channels
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class EmailHistory(Base):
    """Customer email conversations with context for LLM."""

    __tablename__ = "email_history"

    id = Column(Integer, primary_key=True)
    customer_email = Column(String(255), nullable=False, index=True)
    sender_category = Column(String(50))
    subject = Column(String(500))
    body = Column(Text, nullable=False)
    our_reply = Column(Text)
    intent = Column(String(100), index=True)
    channel = Column(String(50), default="email")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_customer_timestamp", "customer_email", "timestamp"),
        Index("idx_intent", "intent"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "customer_email": self.customer_email,
            "sender_category": self.sender_category,
            "subject": self.subject,
            "body": self.body,
            "our_reply": self.our_reply,
            "intent": self.intent,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Booking(Base):
    """Appointment bookings across all channels."""

    __tablename__ = "booking"

    id = Column(String(50), primary_key=True)
    customer_email = Column(String(255), nullable=False, index=True)
    slot = Column(DateTime, nullable=False, index=True)
    channel = Column(String(50))
    notes = Column(Text)
    status = Column(String(50), default="confirmed", index=True)
    booked_at = Column(DateTime, default=datetime.utcnow)
    reminder_sent = Column(Boolean, default=False)
    cancellation_reason = Column(Text)
    cancelled_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_customer_slot", "customer_email", "slot"),
        Index("idx_status_date", "status", "booked_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "customer_email": self.customer_email,
            "slot": self.slot.isoformat() if self.slot else None,
            "channel": self.channel,
            "notes": self.notes,
            "status": self.status,
            "booked_at": self.booked_at.isoformat() if self.booked_at else None,
            "reminder_sent": self.reminder_sent,
            "cancellation_reason": self.cancellation_reason,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KnowledgeBase(Base):
    """
    Knowledge base table with item-level versioning.
    Each record represents a version of a specific KB item.

    Composite primary key: (version_id, kb_field, item_key)
    """

    __tablename__ = "knowledge_base"

    version_id = Column(Integer, primary_key=True, nullable=False)
    kb_field = Column(String(50), primary_key=True, nullable=False)
    item_key = Column(String(255), primary_key=True, nullable=False)
    detail = Column(JSON, nullable=False)
    change_description = Column(Text)
    updated_by = Column(String(255))
    is_active = Column(Boolean, default=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_kb_field_active", "kb_field", "is_active"),
        Index("idx_kb_item_active", "kb_field", "item_key", "is_active"),
        Index("idx_timestamp", "timestamp"),
        Index("idx_is_active", "is_active"),
        Index("idx_last_updated", "last_updated"),
    )

    def to_dict(self):
        return {
            "version_id": self.version_id,
            "kb_field": self.kb_field,
            "item_key": self.item_key,
            "detail": self.detail,
            "change_description": self.change_description,
            "updated_by": self.updated_by,
            "is_active": self.is_active,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KBFeedback(Base):
    """Knowledge base update feedback log (audit trail)."""

    __tablename__ = "kb_feedback"

    id = Column(Integer, primary_key=True)
    operation = Column(String(50))
    kb_field = Column(String(100))
    item_key = Column(String(255))
    kb_version_id = Column(Integer)
    customer_question = Column(Text)
    owner_correction = Column(Text)
    service_name = Column(String(255))
    service_description = Column(Text)
    service_price = Column(String(100))
    policy_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["kb_version_id", "kb_field", "item_key"],
            ["knowledge_base.version_id", "knowledge_base.kb_field", "knowledge_base.item_key"],
            name="fk_kb_feedback_knowledge_base",
        ),
        Index("idx_kb_field", "kb_field"),
        Index("idx_created_at", "created_at"),
        Index("idx_created_at_operation", "created_at", "operation"),
        Index("idx_kb_feedback_version_key", "kb_version_id", "kb_field", "item_key"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "operation": self.operation,
            "kb_field": self.kb_field,
            "customer_question": self.customer_question,
            "owner_correction": self.owner_correction,
            "service_name": self.service_name,
            "service_description": self.service_description,
            "service_price": self.service_price,
            "policy_name": self.policy_name,
            "kb_version_id": self.kb_version_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConversationState(Base):
    """Stores lightweight per-conversation state for multi-turn messaging channels."""

    __tablename__ = "conversation_state"

    conversation_id = Column(String(255), primary_key=True)
    channel = Column(String(50), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    last_intent = Column(String(100), index=True)
    awaiting_pricing_service = Column(Boolean, default=False, nullable=False)
    awaiting_booking_details = Column(Boolean, default=False, nullable=False)
    state_data = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_conversation_channel_user", "channel", "user_id"),
    )

    def to_dict(self):
        return {
            "conversation_id": self.conversation_id,
            "channel": self.channel,
            "user_id": self.user_id,
            "last_intent": self.last_intent,
            "awaiting_pricing_service": self.awaiting_pricing_service,
            "awaiting_booking_details": self.awaiting_booking_details,
            "state_data": self.state_data,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }