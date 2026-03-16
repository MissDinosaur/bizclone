"""
Booking Store

Manages booking persistence and retrieval.
Currently uses JSON file storage, can be extended to use database.
"""
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
import config.config as cfg

logger = logging.getLogger(__name__)


class BookingStore:
    """
    Stores and retrieves appointment bookings.
    Persistent storage using JSON files.
    """

    def __init__(self, bookings_dir: str = cfg.BOOKINGS_DIR):
        self.bookings_dir = bookings_dir
        self.bookings_file = os.path.join(bookings_dir, cfg.BOOKINGS_FILE)
        
        os.makedirs(bookings_dir, exist_ok=True)
    
    def create_booking(
        self,
        customer_email: str,
        slot: str,
        channel: str = "email",
        notes: str = ""
    ) -> Dict:
        """
        Create a new booking and persist it.
        Args:
            customer_email: Customer email address
            slot: Booking slot (format: "YYYY-MM-DD HH:MM")
            channel: Channel through which booking was made (email, teams, whatsapp, etc.)
            notes: Additional booking notes   
        Returns:
            Booking record with confirmation details
        """
        booking = {
            "id": self._generate_booking_id(),
            "customer_email": customer_email,
            "slot": slot,
            "channel": channel,
            "notes": notes,
            "status": "confirmed",
            "booked_at": datetime.now().isoformat(),
            "reminder_sent": False
        }
        
        # Append to bookings log
        with open(self.bookings_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(booking) + "\n")
        
        logger.info(f"Booking created: {booking['id']} | Customer: {customer_email} | Slot: {slot}")
        return booking
    
    def get_booking(self, booking_id: str) -> Optional[Dict]:
        """Retrieve a specific booking by ID."""
        if not os.path.exists(self.bookings_file):
            return None
        
        with open(self.bookings_file, "r", encoding="utf-8") as f:
            for line in f:
                booking = json.loads(line)
                if booking["id"] == booking_id:
                    return booking
        
        return None
    
    def get_bookings_by_email(self, customer_email: str) -> List[Dict]:
        """Get all bookings for a customer."""
        bookings = []
        
        if not os.path.exists(self.bookings_file):
            return bookings
        
        with open(self.bookings_file, "r", encoding="utf-8") as f:
            for line in f:
                booking = json.loads(line)
                if booking["customer_email"] == customer_email:
                    bookings.append(booking)
        
        return bookings
    
    def get_booked_slots(self) -> List[str]:
        """Get all currently booked slots."""
        booked_slots = []
        
        if not os.path.exists(self.bookings_file):
            return booked_slots
        
        with open(self.bookings_file, "r", encoding="utf-8") as f:
            for line in f:
                booking = json.loads(line)
                if booking["status"] == "confirmed":
                    booked_slots.append(booking["slot"])
        
        return booked_slots
    
    def cancel_booking(self, booking_id: str, reason: str = "") -> bool:
        """Mark a booking as cancelled."""
        if not os.path.exists(self.bookings_file):
            return False
        
        # Read all bookings
        bookings = []
        with open(self.bookings_file, "r", encoding="utf-8") as f:
            for line in f:
                booking = json.loads(line)
                if booking["id"] == booking_id:
                    booking["status"] = "cancelled"
                    booking["cancellation_reason"] = reason
                    booking["cancelled_at"] = datetime.now().isoformat()
                bookings.append(booking)
        
        # Write back
        with open(self.bookings_file, "w", encoding="utf-8") as f:
            for booking in bookings:
                f.write(json.dumps(booking) + "\n")
        
        print(f"Booking cancelled: {booking_id}")
        return True
    
    def _generate_booking_id(self) -> str:
        """Generate a unique booking ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # Count existing bookings to create a sequential suffix
        count = 0
        if os.path.exists(self.bookings_file):
            with open(self.bookings_file, "r", encoding="utf-8") as f:
                count = len(f.readlines())
        
        return f"BK{timestamp}{count:05d}"
