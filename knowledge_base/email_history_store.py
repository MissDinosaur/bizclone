"""
Email History Store

Manages persistent storage and retrieval of email conversations using SQLAlchemy.
Provides methods to save incoming/outgoing emails and retrieve conversation history
for context-aware LLM reply generation.
"""

import logging
import os
from datetime import datetime
from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from database.orm_models import EmailHistory

logger = logging.getLogger(__name__)


class EmailHistoryStore:
    """Manages email history storage and retrieval."""
    
    def __init__(self, db_url: str = None):
        """
        Initialize the email history store with PostgreSQL.
        Args:
            db_url: PostgreSQL connection URL.
                   Defaults to DATABASE_URL environment variable (required).
        Raises:
            ValueError: If DATABASE_URL is not set or not a valid PostgreSQL URL.
        """
        if db_url is None:
            db_url = os.getenv("DATABASE_URL")
            if not db_url:
                raise ValueError(
                    "DATABASE_URL environment variable is required and must be set. "
                    "Example: postgresql://user:password@host:5432/database"
                )
        
        if not db_url.startswith("postgresql://") and not db_url.startswith("postgres://"):
            raise ValueError(
                f"Invalid database URL. Only PostgreSQL is supported. "
                f"Got: {db_url[:50]}..."
            )
        
        # Initialize database engine
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        
        logger.info("EmailHistoryStore initialized with PostgreSQL database")
    
    def save_email(self, customer_email: str, sender_category: str, subject: str,
                   body: str, our_reply: str = None, intent: str = None,
                   channel: str = "email") -> bool:
        """
        Save an email to history.
        Args:
            customer_email: Customer's email address (for grouping)
            sender_category: "customer" or "support"
            subject: Email subject line
            body: Email body text
            our_reply: Our generated/sent reply (optional, for outgoing emails)
            intent: Detected intent (optional, e.g., "pricing_inquiry")
            channel: Channel name (default: "email")
        Returns:
            True if saved successfully, False otherwise
        """
        session = self.Session()
        try:
            email_record = EmailHistory(
                customer_email=customer_email,
                sender=sender_category,
                subject=subject,
                body=body,
                our_reply=our_reply,
                intent=intent,
                channel=channel,
                timestamp=datetime.utcnow()
            )
            
            session.add(email_record)
            session.commit()
            
            logger.debug(
                f"Saved email from {sender_category} for customer {customer_email} "
                f"(intent: {intent})"
            )
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error saving email: {str(e)}")
            session.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving email: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def update_email_reply(self, customer_email: str, subject: str, updated_reply: str) -> bool:
        """
        Update the reply for a specific email conversation.
        Used when owner modifies the AI-generated reply before sending.
        
        Args:
            customer_email: Customer's email address
            subject: Email subject (to identify the conversation)
            our_reply: Updated reply text
        
        Returns:
            True if updated successfully, False otherwise
        """
        session = self.Session()
        try:
            # Find the most recent email with this subject and customer
            email = session.query(EmailHistory)\
                .filter(EmailHistory.customer_email == customer_email)\
                .filter(EmailHistory.subject == subject)\
                .order_by(desc(EmailHistory.timestamp))\
                .first()
            
            if not email:
                logger.warning(
                    f"Email not found for {customer_email} with subject '{subject}'"
                )
                return False
            
            # Update the reply
            email.our_reply = updated_reply
            session.commit()
            
            logger.debug(f"Updated reply for email from {customer_email}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error updating email reply: {str(e)}")
            session.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating email reply: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_customer_history(self, customer_email: str, limit: int = 5) -> list:
        """
        Retrieve email history for a customer.
        Args:
            customer_email: Customer's email address
            limit: Maximum number of recent emails to retrieve
        Returns:
            List of email records (dicts) in chronological order,
            or empty list if none found or error occurred
        """
        session = self.Session()
        try:
            query = session.query(EmailHistory)\
                .filter(EmailHistory.customer_email == customer_email)
            query = query.filter(EmailHistory.channel == "email")
            
            emails = query\
                .order_by(desc(EmailHistory.timestamp))\
                .limit(limit)\
                .all()
            
            # Convert to dicts and reverse for chronological order
            formatted = [email.to_dict() for email in reversed(emails)]
            
            logger.debug(
                f"Retrieved {len(formatted)} email records for {customer_email}"
            )
            return formatted
            
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving history: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving history: {str(e)}")
            return []
        finally:
            session.close()
    
    def get_conversation_for_prompt(self, customer_email: str, limit: int = 5) -> str:
        """
        Get formatted email history for use in LLM prompts.
        Args:
            customer_email: Customer's email address
            limit: Maximum number of recent emails
        Returns:
            Formatted string with conversation history suitable for LLM prompt
        """
        history = self.get_customer_history(customer_email, limit=limit)
        
        if not history:
            return "No previous email history for this customer."
        
        formatted_lines = ["CUSTOMER EMAIL HISTORY:"]
        formatted_lines.append("-" * 60)
        
        for email in history:
            timestamp = email.get("timestamp", "Unknown")
            sender = email.get("sender", "Unknown").upper()
            subject = email.get("subject", "(no subject)")
            body = email.get("body", "")
            reply = email.get("our_reply", "")
            intent = email.get("intent", "unknown")
            
            formatted_lines.append(f"\n[{timestamp}] {sender}")
            formatted_lines.append(f"Subject: {subject}")
            formatted_lines.append(f"Message: {body}")
            
            if reply:
                formatted_lines.append(f"Our Reply: {reply}")
            
            formatted_lines.append(f"(Intent: {intent})")
            formatted_lines.append("-" * 60)
        
        return "\n".join(formatted_lines)
    
    def clear_history(self, customer_email: str) -> bool:
        """
        Delete all email history for a customer (use with caution!).
        
        Args:
            customer_email: Customer's email address
        
        Returns:
            True if successful, False otherwise
        """
        session = self.Session()
        try:
            session.query(EmailHistory)\
                .filter(EmailHistory.customer_email == customer_email)\
                .delete()
            session.commit()
            
            logger.warning(f"Deleted email history for {customer_email}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error clearing history: {str(e)}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_database_stats(self) -> dict:
        """Get statistics about stored email history."""
        session = self.Session()
        try:
            total_emails = session.query(EmailHistory).count()
            unique_customers = session.query(
                EmailHistory.customer_email
            ).distinct().count()
            
            return {
                "total_emails": total_emails,
                "unique_customers": unique_customers
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {str(e)}")
            return {}
        finally:
            session.close()
