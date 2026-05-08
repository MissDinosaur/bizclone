#!/usr/bin/env python3
"""
Test script to verify appointment slot selection respects customer's time preferences.
Tests the improved LLM booking assistant with relative dates like "next week" and "afternoon".
"""

import sys
import json
from datetime import datetime, timedelta
from scheduling.llm_booking_assistant import LLMBookingAssistant
from scheduling.scheduling_config import SchedulingConfig

def generate_mock_available_slots():
    """Generate available slots for next 14 days."""
    slots = []
    today = datetime.now()
    
    for days_ahead in range(1, 15):
        date = today + timedelta(days=days_ahead)
        # Skip weekends
        if date.weekday() >= 5:
            continue
        # Generate slots for 9 AM - 5 PM (hourly)
        for hour in range(9, 17):
            slot_time = date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slots.append(slot_time.isoformat())
    
    return slots

def test_appointment_slot_selection():
    """Test various customer date/time preferences."""
    
    assistant = LLMBookingAssistant()
    available_slots = generate_mock_available_slots()
    
    test_cases = [
        {
            "description": "Next week, Tuesday or Wednesday, afternoon",
            "email": """
Hi,
I'd like to schedule a general plumbing inspection for our apartment.
Are you available on Tuesday or Wednesday afternoon next week?
Thanks,
Michael Chen
""",
            "customer_email": "michael@example.com",
            "expected_criteria": {
                "day": ["Tuesday", "Wednesday"],
                "week": "next_week",
                "time_range": "afternoon (12:00-17:00)"
            }
        },
        {
            "description": "Next Monday morning",
            "email": """
Can I schedule an appointment for next Monday morning? 
Looking forward to it.
Best,
Sarah
""",
            "customer_email": "sarah@example.com",
            "expected_criteria": {
                "day": "Monday",
                "week": "next_week",
                "time_range": "morning (08:00-12:00)"
            }
        },
        {
            "description": "This Friday afternoon",
            "email": """
Are you available this Friday in the afternoon?
Please let me know.
Thanks
""",
            "customer_email": "tom@example.com",
            "expected_criteria": {
                "day": "Friday",
                "week": "this_week",
                "time_range": "afternoon"
            }
        },
    ]
    
    print("=" * 80)
    print("TESTING APPOINTMENT SLOT SELECTION WITH CUSTOMER TIME PREFERENCES")
    print("=" * 80)
    print(f"Total available slots: {len(available_slots)}")
    print(f"Date range: {available_slots[0]} to {available_slots[-1]}\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['description']}")
        print(f"Customer email:\n{test_case['email']}")
        print(f"Expected criteria: {test_case['expected_criteria']}")
        
        try:
            selected_slot, reasoning = assistant.select_best_appointment_slot(
                customer_email=test_case["customer_email"],
                email_content=test_case["email"],
                available_slots=available_slots
            )
            
            if selected_slot:
                slot_dt = datetime.fromisoformat(selected_slot)
                day_name = slot_dt.strftime("%A")
                time_str = slot_dt.strftime("%I:%M %p")
                hour = slot_dt.hour
                
                print(f"✓ Selected slot: {selected_slot}")
                print(f"  Day: {day_name}, Time: {time_str}")
                print(f"  Reasoning: {reasoning}")
                
                # Validate against expected criteria
                expected = test_case["expected_criteria"]
                is_valid = True
                
                if "day" in expected:
                    expected_days = expected["day"] if isinstance(expected["day"], list) else [expected["day"]]
                    if day_name not in expected_days:
                        print(f"  ⚠ WARNING: Expected day in {expected_days}, got {day_name}")
                        is_valid = False
                
                if "time_range" in expected:
                    expected_range = expected["time_range"]
                    if "afternoon" in expected_range and not (12 <= hour < 17):
                        print(f"  ⚠ WARNING: Expected afternoon (12-17), got {hour}:00")
                        is_valid = False
                    elif "morning" in expected_range and not (8 <= hour < 12):
                        print(f"  ⚠ WARNING: Expected morning (08-12), got {hour}:00")
                        is_valid = False
                
                status = "✓ PASS" if is_valid else "⚠ CHECK"
                print(f"  Status: {status}")
            else:
                print(f"✗ Failed to select slot: {reasoning}")
                
        except Exception as e:
            print(f"✗ Error during slot selection: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("Testing complete. Verify that selected slots match customer's preferences.")
    print("=" * 80)

if __name__ == "__main__":
    test_appointment_slot_selection()


def test_extract_and_filter_early_next_month_preferences():
    """early next month should only keep slots in the first part of next month."""
    assistant = LLMBookingAssistant.__new__(LLMBookingAssistant)

    email = """
Subject: Scheduling request for annual home plumbing check
Body: Hello,
I am interested in booking an annual plumbing inspection for my house.
Do you have availability early next month?
Thanks.
"""

    prefs = assistant._extract_date_preferences_from_email(email)

    assert prefs["preferred_month"] == "next_month"
    assert prefs["preferred_month_part"] == "early"

    now = datetime.now()
    if now.month == 12:
        next_month = 1
        next_year = now.year + 1
    else:
        next_month = now.month + 1
        next_year = now.year

    matching_slot = datetime(next_year, next_month, 5, 13, 0).strftime("%Y-%m-%d %H:%M")
    non_matching_slot = datetime(next_year, next_month, 18, 13, 0).strftime("%Y-%m-%d %H:%M")

    filtered = assistant._filter_slots_by_preferences(
        [matching_slot, non_matching_slot],
        prefs,
    )

    assert matching_slot in filtered
    assert non_matching_slot not in filtered


def test_scheduling_window_is_sixty_days():
    """Booking configuration should allow selection up to 60 days ahead."""
    config = SchedulingConfig()
    assert config.advance_booking_days == 60


def test_reschedule_specific_date_takes_priority_over_context_dates():
    """Explicit target date in reschedule request should dominate filtering."""
    assistant = LLMBookingAssistant.__new__(LLMBookingAssistant)

    email = (
        "Hi,\n"
        "Could you please reschedule this appointment to April 23 morning? "
        "Because I have to work on April 24.\n"
        "Thank you."
    )

    prefs = assistant._extract_date_preferences_from_email(email)
    assert prefs["specific_date"] is not None

    target_date = datetime.fromisoformat(prefs["specific_date"])
    target_slot = target_date.replace(hour=9, minute=0).strftime("%Y-%m-%d %H:%M")

    context_date = target_date.replace(day=24)
    context_slot_1 = context_date.replace(hour=9, minute=0).strftime("%Y-%m-%d %H:%M")
    context_slot_2 = context_date.replace(hour=10, minute=0).strftime("%Y-%m-%d %H:%M")

    slots = [target_slot, context_slot_1, context_slot_2]

    filtered = assistant._filter_slots_by_preferences(slots, prefs)

    assert target_slot in filtered
    assert context_slot_1 not in filtered
    assert context_slot_2 not in filtered


def test_next_thursday_ignores_quoted_thread_old_date():
    """'next Thursday' in latest message should not be overridden by quoted old date."""
    assistant = LLMBookingAssistant.__new__(LLMBookingAssistant)

    email = (
        "Hi,\n"
        "Could you please change the appointment date? Please reschedule it to next Thursday.\n"
        "\n"
        "On Mon, Apr 13, 2026 at 9:00 AM Support wrote:\n"
        "> Current booking: Friday, April 24, 2026 at 10:00 AM\n"
    )

    prefs = assistant._extract_date_preferences_from_email(email)
    assert prefs["specific_date"] is not None
    assert prefs["specific_date"] != "2026-04-24"

    parsed_target = datetime.fromisoformat(prefs["specific_date"])
    assert parsed_target.strftime("%A") == "Thursday"

    thursday_slot = f"{prefs['specific_date']} 10:00"
    friday_slot = "2026-04-24 10:00"

    filtered = assistant._filter_slots_by_preferences(
        [thursday_slot, friday_slot],
        prefs,
    )

    assert thursday_slot in filtered
    assert friday_slot not in filtered
