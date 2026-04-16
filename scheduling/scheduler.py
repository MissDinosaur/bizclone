"""
Scheduling Service

Provides appointment scheduling functionality for all channels.
Manages slot availability, booking creation, and cancellation (database-backed).
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from scheduling.scheduling_config import SchedulingConfig
from scheduling.booking_store_db import BookingStoreDB
from scheduling.calendar_integration import sync_booking_to_calendar, sync_booking_cancellation

logger = logging.getLogger(__name__)


class AppointmentScheduler:
    """
    Centralized appointment scheduling service (database-backed).
    
    Used by all channels (email, teams, whatsapp, call, facebook) to:
    - Check available slots
    - Create bookings
    - Retrieve booking information
    - Handle cancellations
    """

    def __init__(self):
        self.config = SchedulingConfig()
        self.booking_store = BookingStoreDB()

    def check_availability(self, days_ahead: int = 5) -> List[str]:
        """
        Get available appointment slots.
        Args:
            days_ahead: Number of days to generate slots for (default: 5)
        Returns:
            List of available slots in format "YYYY-MM-DD HH:MM"
        """
        # Generate potential slots
        potential_slots = self.config.generate_available_slots(days_ahead)
        
        # Get already booked confirmed slots
        booked_slots = self.booking_store.get_booked_slots(status="confirmed")
        
        # Convert datetime objects to strings for comparison if needed
        booked_slot_strs = [slot.isoformat().split('T')[0] + ' ' + slot.isoformat().split('T')[1][:5] 
                           if hasattr(slot, 'isoformat') else str(slot) 
                           for slot in booked_slots]
        
        # Filter out booked slots
        available_slots = [slot for slot in potential_slots if slot not in booked_slot_strs]
        
        logger.debug(f"Available slots: {len(available_slots)}/{len(potential_slots)} for next {days_ahead} days")
        return available_slots

    def book_slot(
        self,
        customer_email: str,
        slot: str,
        channel: str = "email",
        notes: str = "",
        days_ahead: Optional[int] = None
    ) -> Dict:
        """
        Book an appointment slot for a customer.
        Args:
            customer_email: Customer email address
            slot: The slot to book (format: "YYYY-MM-DD HH:MM")
            channel: Channel through which booking was made
            notes: Additional booking notes
            days_ahead: Number of days to check availability for (default: 14)
        Returns:
            Booking confirmation dictionary
        """
        if days_ahead is None:
            days_ahead = self.config.advance_booking_days

        # Check if slot is available
        available_slots = self.check_availability(days_ahead=days_ahead)
        
        if slot not in available_slots:
            logger.warning(f"Slot {slot} not available for {customer_email}")
            return {
                "status": "failed",
                "reason": "Slot not available",
                "slot": slot,
                "customer": customer_email
            }
        
        # Create booking via database
        try:
            booking = self.booking_store.create_booking(
                booking_id=None,  # Auto-generate in DB
                customer_email=customer_email,
                slot=slot,
                channel=channel,
                notes=notes
            )
            logger.info(f"Booking created: {booking['id']} | Customer: {customer_email} | Slot: {slot}")
            
            # Sync booking to calendar provider if available
            if booking.get("status") == "confirmed":
                sync_success, event_id = sync_booking_to_calendar(
                    booking,
                    staff_id="default_staff",  # Default staff member
                    default_duration=60  # Default appointment duration
                )
                if sync_success and event_id:
                    booking['calendar_event_id'] = event_id
                    logger.info(f"Booking {booking['id']} synced to calendar as event {event_id}")
                else:
                    logger.warning(f"Failed to sync booking {booking['id']} to calendar")
                    # Booking is still successful, calendar sync is optional
            
            return booking
        except Exception as e:
            logger.error(f"Failed to create booking: {str(e)}")
            return {
                "status": "error",
                "reason": str(e),
                "slot": slot,
                "customer": customer_email
            }

    def get_customer_bookings(self, customer_email: str) -> List[Dict]:
        """Get all confirmed bookings for a customer."""
        bookings = self.booking_store.get_customer_bookings(
            customer_email=customer_email,
            status="confirmed"
        )
        logger.debug(f"Retrieved {len(bookings)} bookings for {customer_email}")
        return bookings

    def cancel_booking(self, booking_id: str, reason: str = "") -> bool:
        """
        Cancel an existing booking.
        Returns True if successful, False otherwise.
        """
        success = self.booking_store.cancel_booking(booking_id, reason)
        if success:
            logger.info(f"Booking {booking_id} cancelled: {reason}")
            
            # Sync cancellation to calendar provider
            cancel_success = sync_booking_cancellation(
                booking_id,
                staff_id="default_staff"
            )
            if cancel_success:
                logger.info(f"Booking {booking_id} removed from calendar")
            else:
                logger.warning(f"Failed to remove booking {booking_id} from calendar")
                # Cancellation is still successful even if calendar sync fails
        else:
            logger.warning(f"Failed to cancel booking {booking_id}")
        return success
    
    def mark_reminder_sent(self, booking_id: str) -> bool:
        """Mark that a reminder has been sent for this booking."""
        return self.booking_store.mark_reminder_sent(booking_id)


# Module-level convenience functions for backward compatibility
_scheduler = AppointmentScheduler()

# Module-level convenience functions for backward compatibility
_scheduler = AppointmentScheduler()


def check_availability(days_ahead: int = 5) -> List[str]:
    """
    Check available appointment slots.
    Convenience function that uses the global scheduler instance.
    """
    return _scheduler.check_availability(days_ahead)


def book_slot(
    customer_email: str,
    slot: str,
    channel: str = "email",
    notes: str = "",
    days_ahead: Optional[int] = None,
) -> Dict:
    """
    Book an appointment slot.
    This is a convenience function that uses the global scheduler instance.
    Args:
        customer_email: Customer email address
        slot: The slot to book (format: "YYYY-MM-DD HH:MM")
        channel: Channel through which booking was made
        notes: Additional booking notes
        days_ahead: Number of days to check availability for (default: 14)
    """
    return _scheduler.book_slot(customer_email, slot, channel, notes, days_ahead)


def get_customer_bookings(customer_email: str) -> List[Dict]:
    """Get all bookings for a customer."""
    return _scheduler.get_customer_bookings(customer_email)


def cancel_booking(booking_id: str, reason: str = "") -> bool:
    """Cancel an existing booking."""
    return _scheduler.cancel_booking(booking_id, reason)

def mark_reminder_sent(booking_id: str) -> bool:
    """Mark that a reminder has been sent for this booking."""
    return _scheduler.mark_reminder_sent(booking_id)
