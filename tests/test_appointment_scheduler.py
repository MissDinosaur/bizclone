"""
Tests for AppointmentScheduler
Tests the main appointment scheduling service.
"""
import pytest
import os
from datetime import datetime
from unittest.mock import patch

# Try to import scheduler, but skip tests if database isn't available
try:
    from scheduling.scheduler import AppointmentScheduler, check_availability, book_slot
    SCHEDULER_AVAILABLE = True
except Exception as e:
    SCHEDULER_AVAILABLE = False
    SCHEDULER_ERROR = str(e)


@pytest.mark.skipif(
    not SCHEDULER_AVAILABLE or os.getenv("SKIP_DB_TESTS") == "true",
    reason="Scheduler tests require PostgreSQL database connection"
)
class TestAppointmentScheduler:
    """Test AppointmentScheduler functionality."""

    def setup_method(self):
        """Initialize scheduler with in-memory store and mocked calendar sync."""
        self.scheduler = AppointmentScheduler()

        class _InMemoryBookingStore:
            def __init__(self):
                self._bookings = []

            def get_booked_slots(self, status="confirmed"):
                return [
                    datetime.strptime(b["slot"], "%Y-%m-%d %H:%M")
                    for b in self._bookings
                    if b.get("status") == status
                ]

            def create_booking(self, booking_id, customer_email, slot, channel, notes=""):
                booking = {
                    "id": booking_id or f"BK-{len(self._bookings) + 1}",
                    "customer_email": customer_email,
                    "slot": slot,
                    "channel": channel,
                    "notes": notes,
                    "status": "confirmed",
                }
                self._bookings.append(booking)
                return booking

            def cancel_booking(self, booking_id, reason=""):
                for booking in self._bookings:
                    if booking["id"] == booking_id and booking.get("status") == "confirmed":
                        booking["status"] = "cancelled"
                        booking["cancel_reason"] = reason
                        return True
                return False

            def get_customer_bookings(self, customer_email, status="confirmed"):
                return [
                    b for b in self._bookings
                    if b.get("customer_email") == customer_email and b.get("status") == status
                ]

            def mark_reminder_sent(self, booking_id):
                for booking in self._bookings:
                    if booking["id"] == booking_id:
                        booking["reminder_sent"] = True
                        return True
                return False

        self.scheduler.booking_store = _InMemoryBookingStore()

        self._sync_booking_patch = patch(
            "scheduling.scheduler.sync_booking_to_calendar",
            return_value=(False, None),
        )
        self._sync_cancel_patch = patch(
            "scheduling.scheduler.sync_booking_cancellation",
            return_value=True,
        )
        self._sync_booking_patch.start()
        self._sync_cancel_patch.start()

    def teardown_method(self):
        """Clean up patches."""
        self._sync_booking_patch.stop()
        self._sync_cancel_patch.stop()

    def test_scheduler_initialization(self):
        """Test that scheduler initializes with config and store."""
        assert self.scheduler.config is not None
        assert self.scheduler.booking_store is not None

    def test_check_availability_returns_list(self):
        """Test that check_availability returns a list of slots."""
        slots = self.scheduler.check_availability()
        assert isinstance(slots, list)

    def test_check_availability_has_slots(self):
        """Test that check_availability returns available slots."""
        slots = self.scheduler.check_availability(days_ahead=5)
        assert len(slots) > 0

    def test_check_availability_excludes_booked_slots(self):
        """Test that booked slots are excluded from availability."""
        # Get available slots
        available = self.scheduler.check_availability(days_ahead=14)
        assert len(available) > 0
        
        # Book first available slot
        slot_to_book = available[0]
        booked = self.scheduler.book_slot(
            customer_email="test@example.com",
            slot=slot_to_book,
            channel="email"
        )
        
        assert booked["status"] == "confirmed"
        
        # Check availability again
        slots = self.scheduler.check_availability(days_ahead=14)
        
        # The booked slot should not be in available slots
        assert slot_to_book not in slots

    def test_book_slot_success(self):
        """Test successful slot booking."""
        # Get available slot
        available = self.scheduler.check_availability(days_ahead=5)
        assert len(available) > 0
        slot = available[0]
        
        booking = self.scheduler.book_slot(
            customer_email="test@example.com",
            slot=slot,
            channel="email"
        )
        
        assert booking["status"] == "confirmed"
        assert booking["customer_email"] == "test@example.com"
        assert booking["slot"] == slot
        assert booking["channel"] == "email"

    def test_book_slot_unavailable_slot(self):
        """Test booking an unavailable slot fails."""
        # Get available slots
        available = self.scheduler.check_availability(days_ahead=5)
        assert len(available) > 0
        slot = available[0]
        
        # Book a slot first
        self.scheduler.book_slot(
            customer_email="test1@example.com",
            slot=slot,
            channel="email"
        )
        
        # Try to book the same slot
        booking = self.scheduler.book_slot(
            customer_email="test2@example.com",
            slot=slot,
            channel="email"
        )
        
        assert booking["status"] == "failed"
        assert "not available" in booking["reason"].lower()

#    def test_book_slot_different_channels(self):
#        """Test booking through different channels."""
#        channels = ["email", "teams", "whatsapp", "call", "facebook"]
#        
#        for i, channel in enumerate(channels):
#            booking = self.scheduler.book_slot(
#                customer_email=f"test{i}@example.com",
#                slot=f"2026-03-0{5+i} 10:00",
#                channel=channel
#            )
#            
#            assert booking["channel"] == channel
#            assert booking["status"] == "confirmed"

    def test_cancel_booking(self):
        """Test cancelling a booking."""
        # Get available slot
        available = self.scheduler.check_availability(days_ahead=14)
        assert len(available) > 0
        slot = available[0]
        
        booking = self.scheduler.book_slot(
            customer_email="test@example.com",
            slot=slot,
            channel="email"
        )
        
        # Verify it was booked
        available_after_book = self.scheduler.check_availability(days_ahead=14)
        assert slot not in available_after_book
        
        # Cancel it
        success = self.scheduler.cancel_booking(booking["id"], reason="Customer request")
        assert success is True
        
        # Verify slot is now available again
        available_after_cancel = self.scheduler.check_availability(days_ahead=14)
        assert slot in available_after_cancel

