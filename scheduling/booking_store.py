"""
Booking Store - Database operations for appointment management.
"""

import logging
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from database.orm_models import Booking

logger = logging.getLogger(__name__)


class BookingStoreDB:
    """Manage bookings in database (replaces JSONL storage)."""
    
    def __init__(self, db_url: str = None):
        """
        Initialize booking store with PostgreSQL.
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
        
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("BookingStoreDB initialized with PostgreSQL database")
    
    def _generate_booking_id(self) -> str:
        """Generate unique booking ID in format BKyyyymmdd-hhmmss."""
        now = datetime.utcnow()
        return now.strftime("BK%Y%m%d-%H%M%S")
    
    def create_booking(self, booking_id: str = None, customer_email: str = "",
                      slot: str = "", channel: str = "email", notes: str = "") -> dict:
        """
        Create new booking.
        Args:
            booking_id: Optional booking ID. Auto-generated if None
            customer_email: Customer email address
            slot: Booking slot (string format "YYYY-MM-DD HH:MM" or datetime)
            channel: Channel name (email, teams, whatsapp, etc.)
            notes: Additional notes
        """
        session = self.Session()
        try:
            # Generate booking ID if not provided
            if not booking_id:
                booking_id = self._generate_booking_id()
            
            # Convert slot string to datetime if needed
            if isinstance(slot, str):
                slot_dt = datetime.fromisoformat(slot.replace(" ", "T"))
            else:
                slot_dt = slot
            
            booking = Booking(
                id=booking_id,
                customer_email=customer_email,
                slot=slot_dt,
                channel=channel,
                notes=notes,
                status="confirmed",
                booked_at=datetime.utcnow()
            )
            session.add(booking)
            session.commit()
            
            logger.info(f"Created booking {booking_id} for {customer_email}")
            return booking.to_dict()
        except SQLAlchemyError as e:
            logger.error(f"Error creating booking: {e}")
            session.rollback()
            return None
        except Exception as e:
            logger.error(f"Error parsing slot or creating booking: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def get_booking(self, booking_id: str) -> dict:
        """Get specific booking."""
        session = self.Session()
        try:
            booking = session.query(Booking).filter(Booking.id == booking_id).first()
            return booking.to_dict() if booking else None
        finally:
            session.close()
    
    def get_customer_bookings(self, customer_email: str, status: str = None) -> list:
        """Get all bookings for customer (optionally filtered by status)."""
        session = self.Session()
        try:
            query = session.query(Booking).filter(Booking.customer_email == customer_email)
            if status:
                query = query.filter(Booking.status == status)
            
            bookings = query.order_by(Booking.slot.desc()).all()
            return [b.to_dict() for b in bookings]
        finally:
            session.close()
    
    def get_booked_slots(self, status: str = "confirmed") -> list:
        """Get all booked slots that are still active.

        Filtering by is_active=True ensures that old bookings deactivated
        during rescheduling or cancellation never block new slot creation.
        """
        session = self.Session()
        try:
            bookings = session.query(Booking).filter(
                Booking.status == status,
                Booking.is_active == True
            ).all()
            return [b.slot for b in bookings]
        finally:
            session.close()
    
    def cancel_booking(self, booking_id: str, reason: str = "") -> bool:
        """Cancel booking."""
        session = self.Session()
        try:
            booking = session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                logger.warning(f"Booking {booking_id} not found")
                return False
            
            booking.status = "cancelled"
            booking.cancellation_reason = reason
            booking.cancelled_at = datetime.utcnow()
            session.commit()
            
            logger.info(f"Cancelled booking {booking_id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error cancelling booking: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def mark_reminder_sent(self, booking_id: str) -> bool:
        """Mark reminders as sent."""
        session = self.Session()
        try:
            booking = session.query(Booking).filter(Booking.id == booking_id).first()
            if booking:
                booking.reminder_sent = True
                session.commit()
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error updating reminder: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_stats(self) -> dict:
        """Get booking statistics."""
        session = self.Session()
        try:
            total = session.query(Booking).count()
            confirmed = session.query(Booking).filter(Booking.status == "confirmed").count()
            cancelled = session.query(Booking).filter(Booking.status == "cancelled").count()
            
            return {
                "total_bookings": total,
                "confirmed": confirmed,
                "cancelled": cancelled
            }
        finally:
            session.close()
