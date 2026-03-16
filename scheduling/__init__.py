"""
Scheduling Module

Provides appointment scheduling functionality for all channels.
Includes configuration management, booking persistence, and slot management.
"""

from scheduling.scheduler import (
    AppointmentScheduler,
    check_availability,
    book_slot,
    get_customer_bookings,
    cancel_booking
)

from scheduling.scheduling_config import SchedulingConfig
from scheduling.booking_store_json import BookingStore

__all__ = [
    "AppointmentScheduler",
    "check_availability",
    "book_slot",
    "get_customer_bookings",
    "cancel_booking",
    "SchedulingConfig",
    "BookingStore",
]
