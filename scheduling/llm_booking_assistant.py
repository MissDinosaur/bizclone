"""
LLM-based Intelligent Booking Assistant

Uses LLM to select the best appointment time based on:
1. Time preferences mentioned in emails ("3 PM", "Wednesday", etc.)
2. Customer's past booking habits
3. Service duration in knowledge base
4. Existing appointments in booking table to avoid conflicts
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from llm_engine.llm_client import LLMClient
from scheduling.scheduler import check_availability
from scheduling.scheduling_config import SchedulingConfig
from database.orm_models import Booking
import config.config as cfg

logger = logging.getLogger(__name__)

# Setup database
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


class LLMBookingAssistant:
    """Use LLM to intelligently select appointment time"""
    
    def __init__(self, db_session: Optional[Session] = None):
        """
        Args:
            db_session: SQLAlchemy session (optional, creates new if not provided)
        """
        self.llm_client = LLMClient()
        self.db = db_session or SessionLocal()
        self._owns_session = db_session is None
    
    def __del__(self):
        """Cleanup database session if we created it."""
        if self._owns_session and self.db:
            self.db.close()
    
    def select_best_appointment_slot(
        self,
        customer_email: str,
        email_content: str,
        available_slots: List[str]
    ) -> Tuple[Optional[str], str]:
        """
        Use LLM to intelligently select the best appointment time
        
        Analysis factors:
        1. Time preferences in email ("afternoon", "Wednesday", etc.)
        2. Customer's past booking habits (queried from booking table)
        3. Service duration information in knowledge base
        4. Avoid conflicts with existing appointments
        
        Args:
            customer_email: Customer email address
            email_content: Original email subject and content
            available_slots: List of available time slots ['2026-04-03 10:00', ...]
            
        Returns:
            (selected_slot, reasoning): Selected time and reasoning process
        """
        
        if not available_slots:
            return None, "No available slots"
        
        try:
            # Collect all information for LLM decision-making
            customer_history = self._get_customer_booking_history(customer_email)
            kb_info = self._get_kb_service_info()
            
            # Build LLM prompt
            prompt = self._build_slot_selection_prompt(
                email_content=email_content,
                available_slots=available_slots,
                customer_history=customer_history,
                kb_info=kb_info
            )
            
            # Call LLM
            response = self.llm_client.generate(prompt)
            
            # Parse LLM response
            selected_slot, reasoning = self._parse_slot_selection_response(
                response=response,
                available_slots=available_slots
            )
            
            if not selected_slot and available_slots:
                logger.warning(f"LLM slot selection failed for {customer_email}, using first available")
                selected_slot = available_slots[0]
                reasoning = "LLM selection failed, using first available slot"
            
            return selected_slot, reasoning
            
        except Exception as e:
            logger.error(f"Error in select_best_appointment_slot: {e}", exc_info=True)
            # Fallback to first available slot
            return available_slots[0] if available_slots else None, str(e)
    
    def _get_customer_booking_history(self, customer_email: str) -> Dict:
        """
        Get customer's past booking habits.
        Analyze their preferred time slots and frequency patterns.
        """
        try:
            bookings = self.db.query(Booking).filter(
                Booking.customer_email == customer_email
            ).order_by(Booking.slot.desc()).limit(10).all()
            
            if not bookings:
                return {"count": 0, "message": "No previous bookings"}
            
            # Analyze time preferences
            hour_preference = {}
            day_preference = {}
            
            for booking in bookings:
                if booking.slot:
                    hour = booking.slot.hour
                    day = booking.slot.strftime("%A")
                    
                    hour_preference[hour] = hour_preference.get(hour, 0) + 1
                    day_preference[day] = day_preference.get(day, 0) + 1
            
            # Find the most commonly preferred time
            preferred_hour = max(hour_preference.items(), key=lambda x: x[1])[0] if hour_preference else None
            preferred_day = max(day_preference.items(), key=lambda x: x[1])[0] if day_preference else None
            
            return {
                "count": len(bookings),
                "preferred_hour": preferred_hour,
                "preferred_day": preferred_day,
                "hour_distribution": hour_preference,
                "day_distribution": day_preference,
                "last_booking": bookings[0].slot.isoformat() if bookings else None
            }
            
        except Exception as e:
            logger.error(f"Error getting customer booking history: {e}")
            return {"count": 0, "error": str(e)}
    
    def _get_kb_service_info(self) -> Dict:
        """
        Retrieve service information from scheduling configuration.
        """
        try:
            config = SchedulingConfig()
            return {
                "default_duration_minutes": config.slot_duration_minutes,
                "business_hours_start": config.business_hours_start,
                "business_hours_end": config.business_hours_end,
                "advance_booking_days": config.advance_booking_days,
                "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "break_times": config.break_times,
                "common_services": ["Plumbing Inspection", "Consultation", "Technical Support"]
            }
        except Exception as e:
            logger.error(f"Error getting KB service info: {e}")
            return {
                "default_duration_minutes": 60,
                "business_hours_start": 9,
                "business_hours_end": 18
            }
    
    def _build_slot_selection_prompt(
        self,
        email_content: str,
        available_slots: List[str],
        customer_history: Dict,
        kb_info: Dict
    ) -> str:
        """Build the prompt for LLM to select the best appointment slot.
        
        IMPORTANT: Customer's explicit date/time request takes priority!
        If customer mentions specific date like "April 13", "next Monday", etc.,
        prioritize finding a matching slot on that date.
        """
        
        prompt = f"""
You are a professional booking assistant. Your PRIMARY task is to RESPECT the customer's explicit date/time request.

IMPORTANT RULES:
1. **If customer mentions a SPECIFIC DATE or TIME, prioritize slots matching that date/time**
   Examples: "April 13", "next Monday", "9:00 AM", "morning", "afternoon"
2. Only use other slots if the requested date/time is NOT available
3. Always return the slot from the available list that BEST matches customer's request

[Customer Email Content]
{email_content[:600]}

[Customer's Past Booking Habits]
- Total appointments: {customer_history.get('count', 0)}
- Preferred hour: {customer_history.get('preferred_hour', 'No clear preference')}
- Preferred day: {customer_history.get('preferred_day', 'No clear preference')}
- Last appointment: {customer_history.get('last_booking', 'None')}

[Service Configuration]
- Slot duration: {kb_info.get('default_duration_minutes', 60)} minutes
- Business hours: {kb_info.get('business_hours_start', 9)}:00-{kb_info.get('business_hours_end', 18)}:00
- Working days: {', '.join(kb_info.get('working_days', []))}
- Advance booking: up to {kb_info.get('advance_booking_days', 14)} days

[Available Time Slots]
{json.dumps(available_slots, ensure_ascii=False, indent=2)}

[Your Task]
1. ANALYZE the email for ANY explicit date/time mentions (dates, day names, times, etc.)
2. Extract customer's explicit request if present
3. PRIORITIZE finding a slot that matches the customer's request
4. If exact match not available, find the closest matching slot on the requested date
5. Return JSON with selected slot and clear reasoning

[Return JSON Format] (return ONLY JSON, no other text)
{{
    "customer_explicit_request": "e.g., April 13 at 9:00 AM, or null if not mentioned",
    "selected_slot": "2026-04-13 09:00",
    "reasoning": "Customer explicitly requested April 13 at 9:00 AM, which matches available slot",
    "confidence": 0.95
}}
"""  
        return prompt
    
    def _parse_slot_selection_response(
        self,
        response: str,
        available_slots: List[str]
    ) -> Tuple[Optional[str], str]:
        """Parse LLM's JSON response."""
        
        try:
            # Extract JSON (handle possible Markdown code blocks)
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.startswith("```"):
                json_str = json_str[3:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            
            data = json.loads(json_str.strip())
            selected_slot = data.get("selected_slot")
            reasoning = data.get("reasoning", "")
            customer_explicit_request = data.get("customer_explicit_request")
            
            # Log customer's explicit request if present
            if customer_explicit_request:
                logger.info(f"Customer explicit request: {customer_explicit_request}")
            
            # Validate that selected time is in available slots
            if selected_slot in available_slots:
                return selected_slot, reasoning
            else:
                logger.warning(f"LLM selected slot '{selected_slot}' not in available slots")
                # Try to find the closest matching time
                for slot in available_slots:
                    if slot.startswith(selected_slot[:13]):  # Match date and hour
                        return slot, f"{reasoning} (adjusted from {selected_slot})"
                return None, f"Selected slot {selected_slot} not available"
                
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"Failed to parse LLM slot selection response: {e}\nResponse: {response}")
            return None, str(e)


# Helper function
_booking_assistant = None


def get_booking_assistant(db_session: Optional[Session] = None) -> LLMBookingAssistant:
    """Get global LLMBookingAssistant instance."""
    global _booking_assistant
    if _booking_assistant is None:
        _booking_assistant = LLMBookingAssistant(db_session)
    return _booking_assistant
