"""
Scheduling Service

Provides appointment scheduling functionality for all channels.
Manages slot availability, booking creation, and cancellation.
"""
import logging
from typing import List, Dict, Optional
from scheduling.scheduling_config import SchedulingConfig
from scheduling.booking_store import BookingStore

logger = logging.getLogger(__name__)


class AppointmentScheduler:
    """
    Centralized appointment scheduling service.
    
    Used by all channels (email, teams, whatsapp, call, facebook) to:
    - Check available slots
    - Create bookings
    - Retrieve booking information
    - Handle cancellations
    """

    def __init__(self):
        self.config = SchedulingConfig()
        self.booking_store = BookingStore()

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
        
        # Get already booked slots
        booked_slots = self.booking_store.get_booked_slots()
        
        # Filter out booked slots
        available_slots = [slot for slot in potential_slots if slot not in booked_slots]
        
        logger.debug(f"Available slots: {len(available_slots)}/{len(potential_slots)} for next {days_ahead} days")
        return available_slots

    def book_slot(
        self,
        customer_email: str,
        slot: str,
        channel: str = "email",
        notes: str = ""
    ) -> Dict:
        """
        Book an appointment slot for a customer.
        Args:
            customer_email: Customer email address
            slot: The slot to book (format: "YYYY-MM-DD HH:MM")
            channel: Channel through which booking was made
            notes: Additional booking notes
        Returns:
            Booking confirmation dictionary
        """
        # Check if slot is available
        available_slots = self.check_availability(days_ahead=14)
        
        if slot not in available_slots:
            return {
                "status": "failed",
                "reason": "Slot not available",
                "slot": slot,
                "customer": customer_email
            }
        
        # Create and persist booking
        booking = self.booking_store.create_booking(
            customer_email=customer_email,
            slot=slot,
            channel=channel,
            notes=notes
        )
        
        return booking

    def get_customer_bookings(self, customer_email: str) -> List[Dict]:
        """Get all bookings for a customer."""
        return self.booking_store.get_bookings_by_email(customer_email)

    def cancel_booking(self, booking_id: str, reason: str = "") -> bool:
        """Cancel an existing booking."""
        return self.booking_store.cancel_booking(booking_id, reason)


# Module-level convenience functions for backward compatibility
_scheduler = AppointmentScheduler()


def check_availability(days_ahead: int = 5) -> List[str]:
    """
    Check available appointment slots.
    Convenience function that uses the global scheduler instance.
    """
    return _scheduler.check_availability(days_ahead)


def book_slot(customer_email: str, slot: str, channel: str = "email", notes: str = "") -> Dict:
    """
    Book an appointment slot.
    This is a convenience function that uses the global scheduler instance.
    """
    return _scheduler.book_slot(customer_email, slot, channel, notes)


def get_customer_bookings(customer_email: str) -> List[Dict]:
    """Get all bookings for a customer."""
    return _scheduler.get_customer_bookings(customer_email)


def cancel_booking(booking_id: str, reason: str = "") -> bool:
    """Cancel an existing booking."""
    return _scheduler.cancel_booking(booking_id, reason)
