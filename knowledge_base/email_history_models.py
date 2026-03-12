"""
Database models for BizClone application.

Defines SQLAlchemy models for storing email history and other persistent data.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class EmailHistory(Base):
    """Email history record for customer conversations.
    
    Stores incoming emails from customers and our generated replies to provide
    context for future LLM-generated responses.
    """
    __tablename__ = "email_history"
    
    id = Column(Integer, primary_key=True)
    customer_email = Column(String(255), nullable=False, index=True)  # Email to query
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # When email arrived
    sender = Column(String(255), nullable=False)  # "customer" or "support"
    subject = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    our_reply = Column(Text, nullable=True)  # Generated reply (null for incoming emails)
    intent = Column(String(100), nullable=True)  # Detected intent (e.g., "pricing_inquiry")
    channel = Column(String(50), default="email")  # Which channel (email, whatsapp, teams, etc.)
    
    # Composite index for efficient history queries
    __table_args__ = (
        Index('idx_customer_timestamp', 'customer_email', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<EmailHistory(id={self.id}, customer={self.customer_email}, timestamp={self.timestamp})>"
    
    def to_dict(self):
        """Convert to dictionary for prompt formatting."""
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
