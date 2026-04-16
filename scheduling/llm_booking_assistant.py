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
        if getattr(self, "_owns_session", False) and getattr(self, "db", None):
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
            # CRITICAL: Extract date/time preferences from email BEFORE passing to LLM
            # This prevents LLM from misunderstanding relative dates like "next week"
            date_preferences = self._extract_date_preferences_from_email(email_content)
            
            # Filter available slots based on extracted preferences
            filtered_slots = self._filter_slots_by_preferences(available_slots, date_preferences)
            
            if not filtered_slots:
                if self._has_strict_date_constraints(date_preferences):
                    logger.warning(
                        "No slots match explicit customer preferences: %s",
                        date_preferences,
                    )
                    return None, "No available slots match the customer's explicit date preferences"

                # If filtering results in no slots and there are no strict date
                # constraints, broaden to all available slots.
                logger.warning(f"No slots match customer preferences: {date_preferences}, using all available slots")
                filtered_slots = available_slots
            else:
                logger.info(f"Filtered {len(available_slots)} slots to {len(filtered_slots)} matching customer preferences: {date_preferences}")
            
            # Collect all information for LLM decision-making
            customer_history = self._get_customer_booking_history(customer_email)
            kb_info = self._get_kb_service_info()
            
            # Build LLM prompt - now with pre-filtered slots
            prompt = self._build_slot_selection_prompt(
                email_content=email_content,
                available_slots=filtered_slots,  # Use pre-filtered slots
                customer_history=customer_history,
                kb_info=kb_info,
                date_constraints=date_preferences  # Pass extracted preferences for reference
            )
            
            # Call LLM
            response = self.llm_client.generate(prompt)
            
            # Parse LLM response
            selected_slot, reasoning = self._parse_slot_selection_response(
                response=response,
                available_slots=filtered_slots  # Validate against filtered slots
            )
            
            if not selected_slot and filtered_slots:
                logger.warning(f"LLM slot selection failed for {customer_email}, using first available from filtered slots")
                selected_slot = filtered_slots[0]
                reasoning = "LLM selection failed, using first available slot matching customer preferences"
            
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
    
    def _extract_date_preferences_from_email(self, email_content: str) -> Dict:
        """
        Extract explicit date/time preferences from customer email BEFORE LLM processing.
        This prevents LLM from misunderstanding relative dates.
        
        Returns:
            Dict with extracted preferences like:
            {
                "preferred_days": ["Tuesday", "Wednesday"],
                "preferred_week": "next_week" | "this_week" | None,
                "preferred_month": "next_month" | "this_month" | None,
                "preferred_month_part": "early" | "mid" | "late" | None,
                "preferred_times": ["afternoon"] | ["morning"] | None,
                "specific_date": "2026-04-15" | None
            }
        """
        import re
        
        customer_text = self._extract_latest_customer_message(email_content)
        content_lower = customer_text.lower()
        prefs = {
            "preferred_days": [],
            "preferred_week": None,
            "preferred_month": None,
            "preferred_month_part": None,
            "preferred_times": [],
            "specific_date": None
        }

        # Extract explicit target date first (e.g. "reschedule ... to April 23").
        # This should take precedence over weaker context such as "next week"
        # from the subject line or additional dates in explanation clauses.
        explicit_date = self._extract_specific_date_from_text(customer_text)
        if not explicit_date:
            explicit_date = self._extract_relative_weekday_from_text(customer_text)
        if explicit_date:
            prefs["specific_date"] = explicit_date
        
        # Extract week preference
        if "next week" in content_lower:
            prefs["preferred_week"] = "next_week"
        elif "this week" in content_lower:
            prefs["preferred_week"] = "this_week"

        # Extract month preference
        if "next month" in content_lower:
            prefs["preferred_month"] = "next_month"
        elif "this month" in content_lower:
            prefs["preferred_month"] = "this_month"

        # Extract month part preference
        if any(phrase in content_lower for phrase in ["early next month", "early this month"]):
            prefs["preferred_month_part"] = "early"
        elif any(phrase in content_lower for phrase in ["mid next month", "middle of next month", "mid-month"]):
            prefs["preferred_month_part"] = "mid"
        elif any(phrase in content_lower for phrase in ["late next month", "end of next month", "later next month"]):
            prefs["preferred_month_part"] = "late"
        
        # Extract day preferences
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        for day in day_names:
            if day in content_lower:
                prefs["preferred_days"].append(day.capitalize())
        
        # Extract time preferences using explicit words or real time expressions.
        # Avoid substring matching such as "I am" being misread as "am".
        if (
            "morning" in content_lower
            or re.search(r"\b(?:8|9|10|11)(?::[0-5]\d)?\s*am\b", content_lower)
        ):
            prefs["preferred_times"].append("morning")
        if (
            "afternoon" in content_lower
            or "noon" in content_lower
            or re.search(
                r"\b(?:12|1|2|3|4)(?::[0-5]\d)?\s*pm\b",
                content_lower,
            )
        ):
            prefs["preferred_times"].append("afternoon")
        if (
            "evening" in content_lower
            or "tonight" in content_lower
            or re.search(r"\b(?:5|6|7|8)(?::[0-5]\d)?\s*pm\b", content_lower)
        ):
            prefs["preferred_times"].append("evening")
        
        logger.info(f"Extracted date preferences from email: {prefs}")
        return prefs

    def _extract_latest_customer_message(self, email_content: str) -> str:
        """Extract the latest customer-authored content before quoted history."""
        import re

        if not email_content:
            return ""

        text = email_content.strip()

        quote_markers = [
            r"\nOn .+ wrote:",
            r"\n-----Original Message-----",
            r"\nFrom:\s",
            r"\nSent:\s",
            r"\n_{5,}\n",
        ]

        for marker in quote_markers:
            match = re.search(marker, text, flags=re.IGNORECASE)
            if match:
                text = text[: match.start()].strip()
                break

        # Remove inline quoted lines like "> previous message".
        filtered_lines = [
            line for line in text.splitlines() if not line.lstrip().startswith(">")
        ]
        return "\n".join(filtered_lines).strip()

    def _extract_relative_weekday_from_text(self, email_content: str) -> Optional[str]:
        """Extract phrases like 'next Thursday' and convert to ISO date."""
        import re

        text = email_content.lower()
        weekday_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
        }

        match = re.search(
            r"\b(next|this)\s+(monday|tuesday|wednesday|thursday|friday)\b",
            text,
        )
        if not match:
            return None

        qualifier = match.group(1)
        weekday_name = match.group(2)
        return self._resolve_weekday_date(weekday_map[weekday_name], qualifier)

    def _resolve_weekday_date(self, target_weekday: int, qualifier: str) -> str:
        """Resolve weekday+qualifier to concrete date string (YYYY-MM-DD)."""
        today = datetime.now().date()
        days_until = (target_weekday - today.weekday()) % 7

        if qualifier == "next":
            # Always pick a future day for "next <weekday>".
            days_until = days_until or 7

        return (today + timedelta(days=days_until)).strftime("%Y-%m-%d")

    def _has_strict_date_constraints(self, prefs: Dict) -> bool:
        """Return True when customer explicitly constrained date/day window."""
        return bool(
            prefs.get("specific_date")
            or prefs.get("preferred_week")
            or prefs.get("preferred_month")
            or prefs.get("preferred_month_part")
            or prefs.get("preferred_days")
        )

    def _extract_specific_date_from_text(self, email_content: str) -> Optional[str]:
        """Extract a customer's explicitly requested target date in ISO format.

        Priority is given to dates that follow rescheduling verbs with "to".
        Example: "Could you please reschedule this appointment to April 23 morning?"
        should extract 2026-04-23 even if another date appears later in the email.
        """
        import re

        text = email_content.strip()
        month_name = (
            r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
            r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
            r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        )
        date_token = rf"({month_name}\s+\d{{1,2}}(?:,\s*\d{{4}})?)"

        prioritized_patterns = [
            # Strong signal: target date after rescheduling action and "to"
            rf"(?:reschedul(?:e|ing)|move|change|shift|postpone)[^.\n]{{0,140}}?\bto\s+{date_token}",
            # Generic fallback: first date after prepositions often used for requested slot
            rf"\b(?:to|on|for)\s+{date_token}",
        ]

        candidate = None
        for pattern in prioritized_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1)
                break

        if not candidate:
            # ISO fallback if customer directly writes 2026-04-23
            iso_match = re.search(r"\b(\d{4}-\d{1,2}-\d{1,2})\b", text)
            if iso_match:
                candidate = iso_match.group(1)

        if not candidate:
            return None

        candidate_clean = re.sub(r"\s+", " ", candidate.strip())

        # Try textual month formats first.
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d", "%b %d"):
            try:
                parsed = datetime.strptime(candidate_clean, fmt)
                if "%Y" not in fmt:
                    today = datetime.now()
                    parsed = parsed.replace(year=today.year)
                    # If date already passed this year, assume next year.
                    if parsed.date() < today.date() - timedelta(days=1):
                        parsed = parsed.replace(year=today.year + 1)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # Try ISO-like numeric format as final fallback.
        try:
            parsed_iso = datetime.fromisoformat(candidate_clean)
            return parsed_iso.strftime("%Y-%m-%d")
        except ValueError:
            return None
    
    def _filter_slots_by_preferences(self, available_slots: List[str], prefs: Dict) -> List[str]:
        """
        Filter available slots based on extracted customer preferences.
        This ensures we NEVER recommend slots that contradict customer's explicit request.
        
        Returns:
            List of slots matching the customer's preferences
        """
        today = datetime.now()
        current_week_start = today - timedelta(days=today.weekday())
        next_week_start = current_week_start + timedelta(days=7)

        current_month = today.month
        current_year = today.year
        if current_month == 12:
            next_month = 1
            next_month_year = current_year + 1
        else:
            next_month = current_month + 1
            next_month_year = current_year
        
        filtered = []
        specific_date = prefs.get("specific_date")
        
        for slot in available_slots:
            try:
                slot_dt = datetime.fromisoformat(slot)

                # If customer explicitly requested a date, that date has highest priority.
                if specific_date and slot_dt.strftime("%Y-%m-%d") != specific_date:
                    continue
                
                # Filter by week if specified
                if not specific_date and prefs.get("preferred_week") == "next_week":
                    # Must be in next week (Monday-Friday)
                    if slot_dt.date() < next_week_start.date() or slot_dt.weekday() >= 5:
                        continue  # Not in next week, skip
                elif not specific_date and prefs.get("preferred_week") == "this_week":
                    # Must be in this week (today through Friday)
                    if slot_dt.date() < today.date() or slot_dt.weekday() >= 5:
                        continue  # Not in this week, skip

                # Filter by month if specified
                if not specific_date and prefs.get("preferred_month") == "next_month":
                    if (
                        slot_dt.month != next_month
                        or slot_dt.year != next_month_year
                    ):
                        continue
                elif not specific_date and prefs.get("preferred_month") == "this_month":
                    if (
                        slot_dt.month != current_month
                        or slot_dt.year != current_year
                    ):
                        continue

                # Filter by month part if specified
                if not specific_date and prefs.get("preferred_month_part") == "early" and slot_dt.day > 10:
                    continue
                if not specific_date and prefs.get("preferred_month_part") == "mid" and not (11 <= slot_dt.day <= 20):
                    continue
                if not specific_date and prefs.get("preferred_month_part") == "late" and slot_dt.day < 21:
                    continue
                
                # Filter by day if specified
                if not specific_date and prefs.get("preferred_days"):
                    slot_day = slot_dt.strftime("%A")
                    if slot_day not in prefs["preferred_days"]:
                        continue  # Not a preferred day, skip
                
                # Filter by time if specified
                hour = slot_dt.hour
                if prefs.get("preferred_times"):
                    time_match = False
                    for time_pref in prefs["preferred_times"]:
                        if time_pref == "morning" and 8 <= hour < 12:
                            time_match = True
                        elif time_pref == "afternoon" and 12 <= hour < 17:
                            time_match = True
                        elif time_pref == "evening" and 17 <= hour < 19:
                            time_match = True
                    if not time_match:
                        continue  # Not a preferred time, skip
                
                # All filters passed, include this slot
                filtered.append(slot)
                
            except Exception as e:
                logger.warning(f"Error filtering slot {slot}: {e}")
                continue
        
        return filtered
    
    def _build_slot_selection_prompt(
        self,
        email_content: str,
        available_slots: List[str],
        customer_history: Dict,
        kb_info: Dict,
        date_constraints: Dict = None
    ) -> str:
        """Build the prompt for LLM to select the best appointment slot.
        
        NOTE: Date/week/day filtering is now done in code (_filter_slots_by_preferences),
        so LLM only needs to pick the best slot from pre-filtered options.
        This eliminates LLM confusion about relative dates.
        """
        
        # Get today's date for reference
        today = datetime.now()
        
        prompt = f"""
You are a professional booking assistant. Your task is to SELECT THE BEST APPOINTMENT SLOT for the customer.

TODAY'S DATE: {today.strftime('%A, %B %d, %Y')}

IMPORTANT: The available slots have already been filtered to match the customer's explicit preferences.
You only need to SELECT THE BEST SLOT from the provided list - do not worry about date/time filtering.

[Customer Email Content]
{email_content[:600]}

[Available Slots - Already Filtered to Match Customer Preferences]
{json.dumps(available_slots, ensure_ascii=False, indent=2)}

[Customer's Past Booking Habits]
- Total appointments: {customer_history.get('count', 0)}
- Preferred hour: {customer_history.get('preferred_hour', 'No clear preference')}
- Preferred day: {customer_history.get('preferred_day', 'No clear preference')}

[Business Hours]
- {kb_info.get('business_hours_start', 9)}:00 - {kb_info.get('business_hours_end', 18)}:00

[Your Task]
1. Review the pre-filtered available slots
2. Consider customer's booking history (if any) for time preferences
3. Select the BEST slot that:
   - Is earliest if customer wants ASAP
   - Matches time preferences (morning/afternoon/evening) if customer has them
   - Matches customer's past booking patterns if available
4. Return the selected slot with brief reasoning

[Return JSON Format - ONLY valid JSON]
{{
    "selected_slot": "2026-04-22 14:00",
    "reason": "This slot matches the customer's preference for next week Wednesday afternoon",
    "confidence": 0.95
}}
"""
        return prompt
    
    def _parse_slot_selection_response(
        self,
        response: str,
        available_slots: List[str]
    ) -> Tuple[Optional[str], str]:
        """Parse LLM's JSON response with detailed analysis."""
        
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
            reasoning = data.get("reason") or data.get("reasoning", "")
            customer_explicit_request = data.get("customer_explicit_request")
            time_filters = data.get("time_filters_applied", {})
            
            # Log customer's explicit request for debugging
            if customer_explicit_request and customer_explicit_request.lower() != "none":
                logger.info(f"Customer explicit request: {customer_explicit_request}")
                logger.info(f"Time filters applied: {time_filters}")
            
            # Log the LLM's analysis steps
            analysis = data.get("analysis")
            if analysis:
                logger.debug(f"LLM Analysis: {analysis}")
            
            # Validate that selected time is in available slots
            if selected_slot and selected_slot in available_slots:
                logger.info(f"Selected slot '{selected_slot}' matches available slots")
                return selected_slot, reasoning
            else:
                if selected_slot:
                    logger.warning(f"LLM selected slot '{selected_slot}' not in available slots, trying to find match")
                    # Try to find the closest matching time (same date, closest hour)
                    slot_date = selected_slot[:10]  # YYYY-MM-DD
                    for slot in available_slots:
                        if slot.startswith(slot_date):
                            logger.info(f"Found matching date, using closest time: {slot}")
                            return slot, f"{reasoning} (time adjusted to available slot)"
                
                # If no date match, use first available and explain
                if available_slots:
                    logger.warning(f"Could not find matching slot for '{selected_slot}', using first available")
                    return available_slots[0], f"Could not match requested time. Using first available: {available_slots[0]}"
                
                return None, "No slots available"
                
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"Failed to parse LLM slot selection response: {e}\nResponse:\n{response}")
            return None, f"Failed to parse LLM response: {str(e)}"


# Helper function
_booking_assistant = None


def get_booking_assistant(db_session: Optional[Session] = None) -> LLMBookingAssistant:
    """Get global LLMBookingAssistant instance."""
    global _booking_assistant
    if _booking_assistant is None:
        _booking_assistant = LLMBookingAssistant(db_session)
    return _booking_assistant
