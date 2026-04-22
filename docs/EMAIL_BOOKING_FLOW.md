# Booking Flow

## Overview

When a customer emails about booking:
1. Intent detection → "appointment"
2. LLM selects best time (email preferences + customer history + availability)
3. Create booking record
4. Generate .ics calendar file
5. Send confirmation via Gmail
6. Display on /calendar UI

---

## Flow Diagram

```
Customer Email
    ↓
email_agent.py: Intent Detection
    ├─ Is intent = "appointment"? 
    └─ YES → _handle_booking_request()
    
    ↓
Check Available Slots
    ├─ check_availability(days_ahead=5)
    ├─ Filter: working hours, no breaks, not booked
    └─ Return: ["2026-04-03 09:00", "2026-04-03 10:00", ...]
    
    ↓
LLM Intelligent Selection (llm_booking_assistant.py)
    ├─ Parse email preferences: "afternoon", "Wednesday", "ASAP"  
    ├─ Query customer history: past booking times/patterns
    ├─ Get KB service info: duration, type
    └─ Return: selected_slot + reasoning
    
    ↓
Create Booking (scheduler.py)
    ├─ book_slot(customer_email, slot, channel="email")
    ├─ Auto-generate ID: BK20260403-090000
    ├─ Store in database
    └─ Sync to calendar if accounts active
    
    ↓
Generate iCalendar (.ics)
    ├─ Create VEVENT with:
    │  ├─ DTSTART: selected appointment time
    │  ├─ SUMMARY: service description
    │  ├─ ATTENDEE: customer email
    │  └─ ORGANIZER: company email
    └─ Encode to UTF-8
    
    ↓
Send Confirmation Email
    ├─ To: customer_email
    ├─ Subject: "Your appointment confirmed"
    ├─ Body: HTML with booking details
    ├─ Attachment: appointment.ics
    └─ Via: Gmail SMTP
    
    ↓
Customer Receives Email
    ├─ Client recognizes .ics attachment
    ├─ Gmail: Show "Add to Calendar" button
    ├─ Outlook: Show accept/decline options
    └─ Other: Allow .ics download/import
    
    ↓
Display on /calendar
    ├─ Fetch all bookings from database
    ├─ Render calendar grid
    ├─ Show booking blocks
    └─ Click for details
```

---

## Key Components

| Component | File | Purpose |
|-----------|------|---------|
| **LLMBookingAssistant** | `scheduling/llm_booking_assistant.py` | AI-powered slot selection based on email + history |
| **AppointmentScheduler** | `scheduling/scheduler.py` | Availability check, booking creation, cancellation |
| **SchedulingConfig** | `scheduling/scheduling_config.py` | Business hours, break times, booking rules |
| **CalendarIntegrationService** | `scheduling/calendar_integration.py` | Sync to Google Calendar / Outlook |
| **BookingStoreDB** | `scheduling/booking_store.py` | PostgreSQL persistence |

---

## Quick Integration in Email Agent

```python
# channels/email/email_agent.py
from scheduling.scheduler import check_availability, book_slot
from scheduling.llm_booking_assistant import LLMBookingAssistant

if detected_intent == "appointment":
    # Get available slots
    available_slots = check_availability(days_ahead=5)
    
    # LLM selects best time
    assistant = LLMBookingAssistant()
    selected_slot, reasoning = assistant.select_best_appointment_slot(
        customer_email=sender_email,
        email_content=email_body,
        available_slots=available_slots
    )
    
    # Create booking (auto-syncs to calendar if active)
    booking = book_slot(
        customer_email=sender_email,
        slot=selected_slot,
        channel="email",
        notes=f"LLM reasoning: {reasoning}"
    )
    
    # Send confirmation
    send_booking_email(
        customer_email=sender_email,
        appointment_slot=selected_slot,
        booking_id=booking['id']
    )
```

---

## Configuration

**Business Hours** (in `scheduling_config.py`):
```python
working_days = [0,1,2,3,4]         # Mon-Fri
business_hours_start = 9           # 9 AM
business_hours_end = 18            # 6 PM
break_times = [{"start": 12, "end": 13}]  # Lunch
slot_duration_minutes = 60         # 1-hour appointments
advance_booking_days = 14          # Max 14 days ahead
min_booking_notice_hours = 24      # Min 24 hours notice
```

**Calendar Sync**:
- Automatically syncs when `CalendarAccount.is_active = TRUE`
- Supports Google Calendar + Outlook
- Creates/removes events seamlessly

---

## Example Flow Trace

**Input Email:**
```
From: john@customer.com
Subject: Want to book afternoon appointment
Body: I want a consultation afternoon if possible
```

**Processing:**
```
1. Intent: "appointment" ✓
2. Available slots: 10 slots in next 5 days
3. LLM analysis:
   - Email keyword: "afternoon" → prefer 14:00-17:00
   - Customer history: 5 past bookings, 4 at 14:00
   - Decision: Select 2026-04-04 14:00
4. Create booking: ID BK20260404-140000
5. Generate .ics: 60-minute event
6. Send email with .ics attachment
7. Database updated + Calendar synced (if active)
```

**Output Email:**
```
To: john@customer.com
Subject: Your appointment confirmed
Body: Your appointment: 2026-04-04 14:00
Attachment: appointment.ics
```
