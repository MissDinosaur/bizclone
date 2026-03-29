"""
Tests for AppointmentScheduler
Tests the main appointment scheduling service.
"""
import pytest
import tempfile
import shutil
from scheduling.scheduler import AppointmentScheduler, check_availability, book_slot


class TestAppointmentScheduler:
    """Test AppointmentScheduler functionality."""

    def setup_method(self):
        """Initialize scheduler with temporary bookings directory."""
        self.test_dir = tempfile.mkdtemp()
        self.scheduler = AppointmentScheduler()
        # Override with test directory
        self.scheduler.booking_store.bookings_dir = self.test_dir
        self.scheduler.booking_store.bookings_file = f"{self.test_dir}/bookings.jsonl"

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

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

