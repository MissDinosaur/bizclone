"""
Tests for BookingStore
Tests booking creation, retrieval, cancellation, and persistence.
"""
import pytest
import os
import tempfile
import shutil
from scheduling.booking_store_json import BookingStore


class TestBookingStore:
    """Test BookingStore functionality."""

    def setup_method(self):
        """Create a temporary directory for test bookings."""
        self.test_dir = tempfile.mkdtemp()
        self.store = BookingStore(bookings_dir=self.test_dir)

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_bookings_directory_created(self):
        """Test that bookings directory is created on init."""
        assert os.path.exists(self.test_dir)

    def test_create_booking_returns_dict(self):
        """Test that create_booking returns a booking dictionary."""
        booking = self.store.create_booking(
            customer_email="test@example.com",
            slot="2026-03-05 10:00"
        )
        
        assert isinstance(booking, dict)
        assert booking["status"] == "confirmed"

    def test_create_booking_generates_unique_id(self):
        """Test that each booking gets a unique ID."""
        booking1 = self.store.create_booking(
            customer_email="test1@example.com",
            slot="2026-03-05 10:00"
        )
        
        booking2 = self.store.create_booking(
            customer_email="test2@example.com",
            slot="2026-03-05 11:00"
        )
        
        assert booking1["id"] != booking2["id"]

    def test_get_booking_by_id(self):
        """Test retrieving a booking by ID."""
        created = self.store.create_booking(
            customer_email="test@example.com",
            slot="2026-03-05 10:00"
        )
        
        retrieved = self.store.get_booking(created["id"])
        
        assert retrieved is not None
        assert retrieved["id"] == created["id"]
        assert retrieved["customer_email"] == "test@example.com"

    def test_get_bookings_by_email(self):
        """Test retrieving all bookings for a customer."""
        self.store.create_booking(
            customer_email="customer@example.com",
            slot="2026-03-05 10:00"
        )
        
        self.store.create_booking(
            customer_email="customer@example.com",
            slot="2026-03-06 11:00"
        )
        
        self.store.create_booking(
            customer_email="other@example.com",
            slot="2026-03-07 14:00"
        )
        
        bookings = self.store.get_bookings_by_email("customer@example.com")
        
        assert len(bookings) == 2
        assert all(b["customer_email"] == "customer@example.com" for b in bookings)

    def test_get_booked_slots(self):
        """Test retrieving all booked slots."""
        self.store.create_booking(
            customer_email="test1@example.com",
            slot="2026-03-05 10:00"
        )
        
        self.store.create_booking(
            customer_email="test2@example.com",
            slot="2026-03-05 11:00"
        )
        
        booked_slots = self.store.get_booked_slots()
        
        assert len(booked_slots) >= 2
        assert "2026-03-05 10:00" in booked_slots
        assert "2026-03-05 11:00" in booked_slots

    def test_get_booked_slots_excludes_cancelled(self):
        """Test that cancelled bookings are not in booked slots."""
        booking = self.store.create_booking(
            customer_email="test@example.com",
            slot="2026-03-05 10:00"
        )
        
        # Verify it's in booked slots
        booked = self.store.get_booked_slots()
        assert "2026-03-05 10:00" in booked
        
        # Cancel it
        self.store.cancel_booking(booking["id"])
        
        # Verify it's no longer in booked slots
        booked = self.store.get_booked_slots()
        assert "2026-03-05 10:00" not in booked

    def test_cancel_booking(self):
        """Test cancelling a booking."""
        booking = self.store.create_booking(
            customer_email="test@example.com",
            slot="2026-03-05 10:00"
        )
        
        success = self.store.cancel_booking(booking["id"], reason="Customer request")
        
        assert success is True
        
        # Verify cancellation
        retrieved = self.store.get_booking(booking["id"])
        assert retrieved["status"] == "cancelled"
        assert retrieved.get("cancellation_reason") == "Customer request"

    def test_booking_persisted_to_file(self):
        """Test that bookings are persisted to JSONL file."""
        self.store.create_booking(
            customer_email="test@example.com",
            slot="2026-03-05 10:00"
        )
        
        # Check that file exists
        assert os.path.exists(self.store.bookings_file)
        
        # Check that file contains booking data
        with open(self.store.bookings_file, "r") as f:
            content = f.read()
            assert "test@example.com" in content
            assert "2026-03-05 10:00" in content

    def test_multiple_bookings_same_customer_different_slots(self):
        """Test multiple bookings for same customer with different slots."""
        customer = "multi@example.com"
        
        booking1 = self.store.create_booking(
            customer_email=customer,
            slot="2026-03-05 10:00"
        )
        
        booking2 = self.store.create_booking(
            customer_email=customer,
            slot="2026-03-06 14:00"
        )
        
        bookings = self.store.get_bookings_by_email(customer)
        assert len(bookings) == 2
        assert any(b["slot"] == "2026-03-05 10:00" for b in bookings)
        assert any(b["slot"] == "2026-03-06 14:00" for b in bookings)

