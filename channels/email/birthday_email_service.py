"""
Birthday Email Service - Sends automated birthday greetings to customers.

Handles:
- Finding customers with upcoming birthdays
- Generating personalized birthday emails
- Sending emails via Gmail client
- Tracking email sending status
"""

import logging
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.orm_models import Customer
from channels.email.gmail_client import GmailClient

logger = logging.getLogger(__name__)


class BirthdayEmailService:
    """Service to send automated birthday greetings to customers."""
    
    def __init__(self, gmail_client: GmailClient = None):
        """
        Initialize birthday email service.
        
        Args:
            gmail_client: GmailClient instance for sending emails.
                         If None, a new instance will be created.
        """
        self.gmail_client = gmail_client or GmailClient()
    
    def get_birthday_customers(self, session: Session, days_ahead: int = 0) -> list:
        """
        Get customers with birthdays today or in the next N days.
        
        Args:
            session: SQLAlchemy session
            days_ahead: Number of days ahead to check (0 = today only, 1 = today and tomorrow, etc.)
        
        Returns:
            List of Customer objects with upcoming birthdays
        """
        today = date.today()
        birthday_customers = []
        
        try:
            # Get all customers with notification enabled
            customers = session.query(Customer).filter(
                Customer.notification_opt_in == True,
                Customer.date_of_birth.isnot(None)
            ).all()
            
            for customer in customers:
                if customer.date_of_birth:
                    # Compare month and day only (ignore year, handles leap year)
                    try:
                        customer_month = customer.date_of_birth.month
                        customer_day = customer.date_of_birth.day
                        today_month = today.month
                        today_day = today.day
                        
                        # Check if today is the customer's birthday (month and day match)
                        is_birthday_today = (customer_month == today_month and customer_day == today_day)
                        
                        if is_birthday_today and days_ahead >= 0:
                            birthday_customers.append(customer)
                            logger.info(f"Found birthday customer: {customer.email} (birthday today!)")
                        elif days_ahead > 0 and not is_birthday_today:
                            # For future dates, calculate the next occurrence of this birthday
                            try:
                                birthday_this_year = customer.date_of_birth.replace(year=today.year)
                                if birthday_this_year < today:
                                    birthday_this_year = customer.date_of_birth.replace(year=today.year + 1)
                                days_until_birthday = (birthday_this_year - today).days
                                if 0 < days_until_birthday <= days_ahead:
                                    birthday_customers.append(customer)
                                    logger.info(f"Found upcoming birthday customer: {customer.email} (in {days_until_birthday} days)")
                            except ValueError:
                                continue
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Error calculating birthday for customer {customer.customer_id}: {e}")
                        continue
            
            return birthday_customers
        
        except Exception as e:
            logger.error(f"Error retrieving birthday customers: {e}")
            return []
    
    def generate_birthday_email(self, customer: Customer) -> tuple:
        """
        Generate personalized birthday email content.
        
        Args:
            customer: Customer object
        
        Returns:
            Tuple of (subject, body)
        """
        full_name = customer.get_full_name() or customer.email
        
        subject = f"🎉 Happy Birthday, {full_name}!"
        
        body = f"""Dear {full_name},

We hope you have a wonderful birthday celebration today! 🎂

Thank you for being a valued customer. We appreciate your continued trust in our services.

As a special gesture, we'd love to help you with:
- Quick booking of our premium services
- Special birthday offers (coming soon)
- Any service inquiries you may have

Feel free to reach out to us anytime. We're here to help!

Best regards,
BizClone Team

---
No reply needed
"""
        
        return subject, body
    
    def send_birthday_emails(self, session: Session, days_ahead: int = 0) -> dict:
        """
        Send birthday emails to all customers with birthdays today/soon.
        
        Args:
            session: SQLAlchemy session
            days_ahead: Number of days ahead to check
        
        Returns:
            Dictionary with sending results:
            {
                "total_customers": int,
                "emails_sent": int,
                "emails_failed": int,
                "sent_to": [email addresses],
                "failed": [{"email": str, "error": str}]
            }
        """
        logger.info(f"Starting birthday email sending process (checking {days_ahead} days ahead)...")
        
        results = {
            "total_customers": 0,
            "emails_sent": 0,
            "emails_failed": 0,
            "sent_to": [],
            "failed": []
        }
        
        try:
            # Get customers with birthdays
            birthday_customers = self.get_birthday_customers(session, days_ahead)
            results["total_customers"] = len(birthday_customers)
            
            if not birthday_customers:
                logger.info("No customers with birthdays to send emails to")
                return results
            
            logger.info(f"Found {len(birthday_customers)} customers with upcoming birthdays")
            
            # Send email to each customer
            for customer in birthday_customers:
                try:
                    subject, body = self.generate_birthday_email(customer)
                    
                    # Send email
                    self.gmail_client.send_email(
                        to_email=customer.email,
                        subject=subject,
                        message=body
                    )
                    
                    # Save birthday email to history
                    from knowledge_base.email_history_store import EmailHistoryStore
                    email_store = EmailHistoryStore()
                    email_store.save_email(
                        customer_email=customer.email,
                        sender_category="happy birthday",
                        subject=subject,
                        body=body,
                        thread_id=None,  # Birthday emails are not part of a conversation thread
                        message_id=None,  # No message ID for automated birthday emails
                        intent=None,
                        channel="email"
                    )
                    
                    # Update last_contacted_at timestamp
                    customer.last_contacted_at = datetime.utcnow()
                    session.add(customer)
                    
                    results["emails_sent"] += 1
                    results["sent_to"].append(customer.email)
                    logger.info(f"Birthday email sent to {customer.email}")
                
                except Exception as e:
                    results["emails_failed"] += 1
                    results["failed"].append({
                        "email": customer.email,
                        "error": str(e)
                    })
                    logger.error(f"Failed to send birthday email to {customer.email}: {e}")
            
            # Commit changes
            session.commit()
            
            logger.info(f"Birthday email sending completed. Sent: {results['emails_sent']}, Failed: {results['emails_failed']}")
            return results
        
        except Exception as e:
            logger.error(f"Error in send_birthday_emails: {e}")
            session.rollback()
            raise
