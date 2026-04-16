"""
Database models for BizClone application using SQLAlchemy.

Defines all persistent data models:
1. EmailHistory - Customer email conversations
2. Booking - Appointment reservations  
3. KnowledgeBase - Knowledge base versions with tracking (merged from kb_version + kb_current)
4. KBFeedback - Knowledge base update log
5. Customer - Customer profiles for personalized service
6. CalendarAccount - OAuth calendar integrations
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Index, JSON, Boolean, ForeignKey, TIMESTAMP, PrimaryKeyConstraint, ForeignKeyConstraint, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class EmailHistory(Base):
    """Customer email conversations with context for LLM."""
    __tablename__ = "email_history"
    
    id = Column(Integer, primary_key=True)
    customer_email = Column(String(255), nullable=False, index=True)
    sender_category = Column(String(50))  # customer, support, or happy birthday category
    subject = Column(String(500))
    body = Column(Text, nullable=False)
    thread_id = Column(String(255))  # Gmail thread ID for conversation grouping
    message_id = Column(String(255))  # Gmail message ID for individual email reference
    intent = Column(String(100), index=True)
    channel = Column(String(50), default="email")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_customer_timestamp', 'customer_email', 'timestamp'),
        Index('idx_intent', 'intent'),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "customer_email": self.customer_email,
            "sender_category": self.sender_category,
            "subject": self.subject,
            "body": self.body,
            "thread_id": self.thread_id,
            "message_id": self.message_id,
            "intent": self.intent,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
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
    is_active = Column(Boolean, default=True, index=True)
    modification_type = Column(String(50), default=None)
    parent_booking_id = Column(String(50), default=None, index=True)
    reschedule_reason = Column(Text)
    modified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_customer_slot', 'customer_email', 'slot'),
        Index('idx_status_date', 'status', 'booked_at'),
        Index('idx_is_active', 'is_active'),
        Index('idx_parent_booking', 'parent_booking_id'),
        Index('idx_customer_active', 'customer_email', 'is_active'),
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
            "is_active": self.is_active,
            "modification_type": self.modification_type,
            "parent_booking_id": self.parent_booking_id,
            "reschedule_reason": self.reschedule_reason,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class KnowledgeBase(Base):
    """
    Knowledge Base table with item-level versioning.
    Each record represents a version of a specific KB item (individual service, policy, or faq).
    Multiple items can share the same version_id when initialized together.
    When an item is updated, a new version_id is created only for that item.
    
    Composite primary key: (version_id, kb_field, item_key)
    """
    __tablename__ = "knowledge_base"
    
    version_id = Column(Integer, primary_key=True, nullable=False)
    kb_field = Column(String(50), primary_key=True, nullable=False)  # 'faq', 'policy', or 'service'
    item_key = Column(String(255), primary_key=True, nullable=False)  # Unique key for this item
    detail = Column(JSON, nullable=False)
    change_description = Column(Text)
    updated_by = Column(String(255))
    is_active = Column(Boolean, default=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_kb_field_active', 'kb_field', 'is_active'),
        Index('idx_kb_item_active', 'kb_field', 'item_key', 'is_active'),
        Index('idx_timestamp', 'timestamp'),
        Index('idx_is_active', 'is_active'),
        Index('idx_last_updated', 'last_updated'),
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
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class KBFeedback(Base):
    """Knowledge base update feedback log (audit trail).
    Foreign Key: (kb_version_id, kb_field, item_key) REFERENCES knowledge_base(version_id, kb_field, item_key)
    """
    __tablename__ = "kb_feedback"
    
    id = Column(Integer, primary_key=True)
    operation = Column(String(50))
    kb_field = Column(String(100))
    item_key = Column(String(255))
    kb_version_id = Column(Integer)  # Part of composite FK
    customer_question = Column(Text)
    owner_correction = Column(Text)
    service_name = Column(String(255))
    service_description = Column(Text)
    service_price = Column(String(100))
    policy_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        ForeignKeyConstraint(
            ['kb_version_id', 'kb_field', 'item_key'],
            ['knowledge_base.version_id', 'knowledge_base.kb_field', 'knowledge_base.item_key'],
            name='fk_kb_feedback_knowledge_base'
        ),
        Index('idx_kb_field', 'kb_field'),
        Index('idx_created_at', 'created_at'),
        Index('idx_created_at_operation', 'created_at', 'operation'),
        Index('idx_kb_feedback_version_key', 'kb_version_id', 'kb_field', 'item_key'),
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
            "created_at": self.created_at.isoformat()
        }

class Customer(Base):
    """Customer profile for personalized service and birthday reminders."""
    __tablename__ = "customer"
    
    customer_id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20))
    date_of_birth = Column(Date, index=True)
    home_address = Column(Text)
    city = Column(String(100))
    state_province = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100))
    preferred_contact_method = Column(String(50), default='email')
    notification_opt_in = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contacted_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_customer_email', 'email'),
        Index('idx_customer_dob', 'date_of_birth'),
        Index('idx_customer_created', 'created_at'),
        Index('idx_customer_contact_pref', 'preferred_contact_method'),
    )
    
    def get_full_name(self):
        """Return customer's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    def to_dict(self):
        """Convert customer object to dictionary."""
        return {
            "customer_id": self.customer_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.get_full_name(),
            "email": self.email,
            "phone": self.phone,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "home_address": self.home_address,
            "city": self.city,
            "state_province": self.state_province,
            "postal_code": self.postal_code,
            "country": self.country,
            "preferred_contact_method": self.preferred_contact_method,
            "notification_opt_in": self.notification_opt_in,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_contacted_at": self.last_contacted_at.isoformat() if self.last_contacted_at else None,
        }


class CalendarAccount(Base):
    """OAuth calendar integration for staff (Google Calendar, Outlook, etc.)."""
    __tablename__ = "calendar_account"
    
    account_id = Column(Integer, primary_key=True)
    staff_id = Column(String(255), nullable=False, index=True)
    provider = Column(String(50), nullable=False)  # 'google', 'outlook'
    email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_calendar_account_provider_email', 'provider', 'email'),
        Index('idx_calendar_account_staff', 'staff_id', 'provider'),
        Index('idx_calendar_account_active', 'is_active'),
    )
    
    def to_dict(self):
        return {
            "account_id": self.account_id,
            "staff_id": self.staff_id,
            "provider": self.provider,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
        }