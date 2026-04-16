"""
Booking Manager - Advanced booking operations
Handles cancellations, reschedules, and deactivation of bookings.
Ensures deactivated bookings don't appear in calendar views.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.orm_models import Booking
from scheduling.scheduler import check_availability, book_slot
from scheduling.scheduling_config import SchedulingConfig
import uuid
import os

logger = logging.getLogger(__name__)


class BookingManager:
    """
    Advanced booking management with support for:
    - Rescheduling appointments (deactivate old, create new)
    - Cancelling appointments (deactivate gracefully)
    - Tracking modification history
    - Filtering for active bookings only in calendar views
    """

    def __init__(self, db_session: Session = None):
        """
        Initialize booking manager.
        
        Args:
            db_session: SQLAlchemy session for database operations (creates new if None)
        """
        self.scheduling_config = SchedulingConfig()
        if db_session:
            self.db = db_session
            self._owns_session = False
        else:
            # Create our own database session if none provided
            try:
                db_url = os.getenv("DATABASE_URL")
                engine = create_engine(db_url, echo=False)
                SessionLocal = sessionmaker(bind=engine)
                self.db = SessionLocal()
                self._owns_session = True
                logger.info("BookingManager created its own database session")
            except Exception as e:
                logger.error(f"Failed to create database session for BookingManager: {e}")
                self.db = None
                self._owns_session = False

    def _get_customer_current_booking(
        self,
        customer_email: str,
        exclude_inactive: bool = True
    ) -> Optional[Booking]:
        """
        Find the customer's current/most recent active booking.
        
        Args:
            customer_email: Customer email
            exclude_inactive: If True, only return active bookings
            
        Returns:
            Booking object or None if not found
        """
        try:
            query = self.db.query(Booking).filter(
                Booking.customer_email == customer_email
            )
            
            if exclude_inactive:
                query = query.filter(Booking.is_active == True)
            
            # Get most recent booking
            booking = query.order_by(Booking.slot.desc()).first()
            return booking
        except Exception as e:
            logger.error(f"Error finding customer booking: {e}")
            return None

    def cancel_appointment(
        self,
        customer_email: str,
        reason: str = "Customer requested cancellation",
        channel: str = "email"
    ) -> Dict:
        """
        Cancel a customer's appointment.
        Steps:
        1. Find customer's current active booking
        2. Mark it as inactive
        3. Record cancellation reason
        4. Update modification info
        
        Args:
            customer_email: Customer email
            reason: Reason for cancellation
            channel: Channel through which cancellation was made
            
        Returns:
            {
                "status": "success" | "error",
                "booking_id": str,
                "message": str,
                "cancelled_at": datetime,
                "details": dict
            }
        """
        try:
            # Find current active booking
            booking = self._get_customer_current_booking(customer_email, exclude_inactive=True)
            
            if not booking:
                logger.warning(f"No active booking found for {customer_email}")
                return {
                    "status": "error",
                    "message": "No active booking found to cancel",
                    "booking_id": None,
                    "details": {}
                }
            
            # Deactivate the booking and update status so it is
            # excluded from calendar queries that filter on status.
            booking.is_active = False
            booking.status = "cancelled"
            booking.modification_type = "cancel"
            booking.cancellation_reason = reason
            booking.cancelled_at = datetime.utcnow()
            booking.modified_at = datetime.utcnow()
            booking.reschedule_reason = reason
            
            self.db.commit()
            
            logger.info(
                f"Booking cancelled: {booking.id} | Customer: {customer_email} | "
                f"Reason: {reason} | Slot was: {booking.slot}"
            )
            
            return {
                "status": "success",
                "booking_id": booking.id,
                "message": f"Appointment on {booking.slot.strftime('%Y-%m-%d %H:%M')} has been cancelled",
                "cancelled_at": booking.cancelled_at,
                "details": {
                    "original_slot": booking.slot.isoformat(),
                    "cancellation_reason": reason,
                    "customer_email": customer_email
                }
            }
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            self.db.rollback()
            return {
                "status": "error",
                "message": f"Error cancelling appointment: {str(e)}",
                "booking_id": None,
                "details": {"error": str(e)}
            }

    def reschedule_appointment(
        self,
        customer_email: str,
        new_slot: str,  # Format: "YYYY-MM-DD HH:MM"
        reason: str = "Customer requested reschedule",
        channel: str = "email"
    ) -> Dict:
        """
        Reschedule a customer's appointment to a new time. 
        Steps:
        1. Get customer's current active booking
        2. Check if new_slot is available
        3. Create new booking for new_slot
        4. Deactivate old booking with parent_booking_id pointing to new one
        5. Link new booking back to old one (parent_booking_id)
        
        Args:
            customer_email: Customer email
            new_slot: New appointment slot (format: "YYYY-MM-DD HH:MM")
            reason: Reason for reschedule
            channel: Channel through which reschedule was made
            
        Returns:
            {
                "status": "success" | "error",
                "old_booking_id": str,
                "new_booking_id": str,
                "message": str,
                "details": dict
            }
        """
        try:
            # Find current active booking
            old_booking = self._get_customer_current_booking(customer_email, exclude_inactive=True)
            
            if not old_booking:
                logger.warning(f"No active booking found for {customer_email}")
                return {
                    "status": "error",
                    "message": "No active booking found to reschedule",
                    "old_booking_id": None,
                    "new_booking_id": None,
                    "details": {}
                }
            
            # Check if new slot is available
            available_slots = check_availability(
                days_ahead=self.scheduling_config.advance_booking_days
            )
            if new_slot not in available_slots:
                logger.warning(f"New slot {new_slot} is not available")
                return {
                    "status": "error",
                    "message": f"Slot {new_slot} is not available. Please choose from available slots.",
                    "old_booking_id": old_booking.id,
                    "new_booking_id": None,
                    "details": {
                        "available_slots": available_slots[:5]  # Show first 5 available slots
                    }
                }
            
            # Create new booking for new slot
            new_booking_result = book_slot(
                customer_email=customer_email,
                slot=new_slot,
                channel=channel,
                notes=f"Rescheduled from {old_booking.slot.strftime('%Y-%m-%d %H:%M')}. Reason: {reason}"
            )
            
            # book_slot returns a dict with the booking data, status is 'confirmed' on success
            if not new_booking_result or new_booking_result.get("status") != "confirmed":
                logger.error(f"Failed to create new booking: {new_booking_result}")
                return {
                    "status": "error",
                    "message": "Failed to create new appointment",
                    "old_booking_id": old_booking.id,
                    "new_booking_id": None,
                    "details": new_booking_result or {}
                }
            
            new_booking_id = new_booking_result["id"]
            
            # Deactivate old booking and mark it as rescheduled.
            # Setting status to 'cancelled' ensures slot-availability checks
            # and calendar queries that filter on status also skip this record.
            old_booking.is_active = False
            old_booking.status = "cancelled"
            old_booking.modification_type = "reschedule"
            old_booking.parent_booking_id = new_booking_id  # Link to new booking
            old_booking.reschedule_reason = reason
            old_booking.modified_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Appointment rescheduled: {old_booking.id} → {new_booking_id} | "
                f"Customer: {customer_email} | "
                f"Old slot: {old_booking.slot} → New slot: {new_slot}"
            )
            
            return {
                "status": "success",
                "old_booking_id": old_booking.id,
                "new_booking_id": new_booking_id,
                "message": f"Appointment rescheduled from {old_booking.slot.strftime('%Y-%m-%d %H:%M')} to {new_slot}",
                "details": {
                    "old_slot": old_booking.slot.isoformat(),
                    "new_slot": new_slot,
                    "reason": reason,
                    "customer_email": customer_email
                }
            }
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}")
            self.db.rollback()
            return {
                "status": "error",
                "message": f"Error rescheduling appointment: {str(e)}",
                "old_booking_id": None,
                "new_booking_id": None,
                "details": {"error": str(e)}
            }

    def get_active_bookings_for_calendar(self, days_ahead: int = 30) -> list:
        """
        Get all ACTIVE bookings for calendar display.
        Only returns bookings with is_active=True.
        
        This ensures deactivated/cancelled/rescheduled bookings don't appear in calendars.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of active Booking objects
        """
        try:
            from datetime import datetime, timedelta
            
            today = datetime.utcnow()
            cutoff_date = today + timedelta(days=days_ahead)
            
            bookings = self.db.query(Booking).filter(
                Booking.is_active == True,  # Only active bookings
                Booking.slot >= today,
                Booking.slot <= cutoff_date,
                Booking.status == "confirmed"  # Only confirmed bookings
            ).order_by(Booking.slot).all()
            
            logger.debug(f"Retrieved {len(bookings)} active bookings for calendar display")
            return bookings
        except Exception as e:
            logger.error(f"Error retrieving active bookings: {e}")
            return []

    def get_booking_history(self, customer_email: str) -> dict:
        """
        Get full booking history including reschedules and cancellations.
        Shows the modification chain for transparency.
    
        Args:
            customer_email: Customer email
            
        Returns:
            {
                "current_booking": Booking | None,
                "past_bookings": [Booking],
                "cancellation_history": [Booking],
                "reschedule_chain": [(old_booking, new_booking), ...]
            }
        """
        try:
            # Current active booking
            current_booking = self._get_customer_current_booking(customer_email, exclude_inactive=True)
            
            # All historical bookings
            all_bookings = self.db.query(Booking).filter(
                Booking.customer_email == customer_email
            ).order_by(Booking.slot.desc()).all()
            
            # Separate by status
            past_bookings = [b for b in all_bookings if b.slot < datetime.utcnow() and b.is_active]
            cancelled_bookings = [b for b in all_bookings if b.modification_type == "cancel"]
            
            # Find reschedule chains (parent → child relationships)
            reschedule_chains = []
            for booking in all_bookings:
                if booking.parent_booking_id:
                    # Find parent
                    parent = self.db.query(Booking).filter(
                        Booking.id == booking.parent_booking_id
                    ).first()
                    if parent:
                        reschedule_chains.append({
                            "from": parent.to_dict(),
                            "to": booking.to_dict(),
                            "reason": booking.reschedule_reason
                        })
            
            return {
                "current_booking": current_booking.to_dict() if current_booking else None,
                "past_bookings": [b.to_dict() for b in past_bookings],
                "cancellation_history": [b.to_dict() for b in cancelled_bookings],
                "reschedule_chain": reschedule_chains
            }
        except Exception as e:
            logger.error(f"Error retrieving booking history: {e}")
            return {
                "current_booking": None,
                "past_bookings": [],
                "cancellation_history": [],
                "reschedule_chain": []
            }
