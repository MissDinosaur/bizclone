"""
Scheduling Configuration

Defines time-based availability, working hours, and slot management.
"""
from datetime import datetime, timedelta
from typing import List


class SchedulingConfig:
    """
    Business scheduling configuration.
    Can be extended to load from database or config file.
    """

    def __init__(self):
        # Working Hours (Monday-Friday, 9 AM - 6 PM)
        self.working_days = [0, 1, 2, 3, 4]  # 0=Monday, 4=Friday
        self.business_hours_start = 9  # 9 AM
        self.business_hours_end = 18  # 6 PM
        
        # Slot Configuration
        self.slot_duration_minutes = 60  # 1-hour slots
        self.advance_booking_days = 14  # Can book up to 14 days in advance
        self.min_booking_notice_hours = 24  # Must book at least 24 hours in advance
        
        # Break Times (12 PM - 1 PM every day)
        self.break_times = [{"start": 12, "end": 13}]  # 12 PM - 1 PM
        
        # Emergency slots (24/7 available)
        self.emergency_slots_per_day = 2
        
    def get_working_hours_range(self) -> tuple:
        """Return (start_hour, end_hour) for business operations."""
        return (self.business_hours_start, self.business_hours_end)
    
    def is_working_day(self, date: datetime) -> bool:
        """Check if a given date is a working day."""
        return date.weekday() in self.working_days
    
    def is_break_time(self, hour: int) -> bool:
        """Check if a given hour falls within a break time."""
        for break_slot in self.break_times:
            if break_slot["start"] <= hour < break_slot["end"]:
                return True
        return False
    
    def is_within_booking_window(self, slot_datetime: datetime) -> bool:
        """Check if slot is within the advance booking window."""
        now = datetime.now()
        slot_time = slot_datetime
        
        # Check minimum notice (must be at least X hours away)
        min_booking_time = now + timedelta(hours=self.min_booking_notice_hours)
        if slot_time < min_booking_time:
            return False
        
        # Check maximum advance booking
        max_booking_time = now + timedelta(days=self.advance_booking_days)
        if slot_time > max_booking_time:
            return False
        
        return True
    
    def generate_available_slots(self, days_ahead: int = 5) -> List[str]:
        """
        Generate available slots for the next N days.
        Args:
            days_ahead: Number of days to generate slots for 
        Returns:
            List of slot strings in format "YYYY-MM-DD HH:MM"
        """
        slots = []
        current_date = datetime.now().date() + timedelta(days=1)  # Start from tomorrow
        
        for _ in range(days_ahead):
            if self.is_working_day(datetime.combine(current_date, datetime.min.time())):
                start_hour = self.business_hours_start
                end_hour = self.business_hours_end
                
                for hour in range(start_hour, end_hour):
                    if not self.is_break_time(hour):
                        slot_time = datetime.combine(current_date, datetime.min.time()).replace(hour=hour)
                        
                        if self.is_within_booking_window(slot_time):
                            slots.append(slot_time.strftime("%Y-%m-%d %H:%M"))
            
            current_date += timedelta(days=1)
        
        return slots
