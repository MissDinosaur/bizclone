"""
Database models for BizClone application using SQLAlchemy.

Defines all persistent data models:
1. EmailHistory - Customer email conversations
2. Booking - Appointment reservations  
3. KnowledgeBase - Knowledge base versions with tracking (merged from kb_version + kb_current)
4. KBFeedback - Knowledge base update log
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Index, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class EmailHistory(Base):
    """Customer email conversations with context for LLM."""
    __tablename__ = "email_history"
    
    id = Column(Integer, primary_key=True)
    customer_email = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    sender = Column(String(50), nullable=False)  # "customer" or "support"
    subject = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    our_reply = Column(Text)
    intent = Column(String(100))
    channel = Column(String(50), default="email")
    
    __table_args__ = (
        Index('idx_customer_timestamp', 'customer_email', 'timestamp'),
        Index('idx_intent', 'intent'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M"),
            "sender": self.sender,
            "subject": self.subject,
            "body": self.body,
            "our_reply": self.our_reply,
            "intent": self.intent,
            "channel": self.channel
        }


class Booking(Base):
    """Appointment bookings across all channels."""
    __tablename__ = "bookings"
    
    id = Column(String(50), primary_key=True)  # BK20260312...
    customer_email = Column(String(255), nullable=False, index=True)
    slot = Column(DateTime, nullable=False, index=True)
    channel = Column(String(50), default="email")
    notes = Column(Text)
    status = Column(String(50), default="confirmed", index=True)  # confirmed, cancelled, completed, no-show
    booked_at = Column(DateTime, default=datetime.utcnow)
    reminder_sent = Column(Boolean, default=False)
    cancellation_reason = Column(Text)
    cancelled_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_customer_slot', 'customer_email', 'slot'),
        Index('idx_status_date', 'status', 'booked_at'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "customer_email": self.customer_email,
            "slot": self.slot.isoformat(),
            "channel": self.channel,
            "notes": self.notes,
            "status": self.status,
            "booked_at": self.booked_at.isoformat(),
            "reminder_sent": self.reminder_sent,
            "cancellation_reason": self.cancellation_reason,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None
        }


class KnowledgeBase(Base):
    """
    Consolidated Knowledge Base table (merged kb_version + kb_current).
    Stores all KB versions with version tracking and active flag.
    """
    __tablename__ = "knowledge_base"
    
    version_id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    kb_data = Column(JSON, nullable=False)  # Full KB JSON snapshot
    services = Column(JSON)  # Cached: {service_id: {name, description, price}}
    policies = Column(JSON)  # Cached: {policy_key: policy_text}
    faqs = Column(JSON)      # Cached: [{q: ..., a: ...}, ...]
    change_description = Column(Text)
    updated_by = Column(String(255))
    is_active = Column(Boolean, default=False, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
        Index('idx_is_active', 'is_active'),
        Index('idx_last_updated', 'last_updated'),
    )
    
    def to_dict(self):
        return {
            "version_id": self.version_id,
            "timestamp": self.timestamp.isoformat(),
            "kb_data": self.kb_data,
            "services": self.services,
            "policies": self.policies,
            "faqs": self.faqs,
            "change_description": self.change_description,
            "updated_by": self.updated_by,
            "is_active": self.is_active,
            "last_updated": self.last_updated.isoformat()
        }


class KBFeedback(Base):
    """Knowledge base update feedback log (audit trail)."""
    __tablename__ = "kb_feedback"
    
    id = Column(Integer, primary_key=True)
    operation = Column(String(50), nullable=False)  # insert, update
    kb_field = Column(String(50), nullable=False)   # service, policy, faq
    customer_question = Column(Text)
    owner_correction = Column(Text)
    service_name = Column(String(255))
    service_description = Column(Text)
    service_price = Column(String(100))
    kb_version_id = Column(Integer, ForeignKey("knowledge_base.version_id"))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_kb_field', 'kb_field'),
        Index('idx_created_at', 'created_at'),
        Index('idx_created_at_operation', 'created_at', 'operation'),
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
            "kb_version_id": self.kb_version_id,
            "created_at": self.created_at.isoformat()
        }
