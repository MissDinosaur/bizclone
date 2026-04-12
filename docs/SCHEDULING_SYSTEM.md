# Scheduling System

## Overview

Comprehensive appointment and event management with PostgreSQL persistence, intelligent slot selection via LLM, and multi-provider calendar integration (Google Calendar, Outlook). Supports all channels: email, Teams, WhatsApp, calls, Facebook.

## Architecture

| Component | Purpose |
|-----------|---------|
| **AppointmentScheduler** | Central service for availability checking, booking, cancellation |
| **BookingStoreDB** | PostgreSQL persistence layer for all bookings |
| **SchedulingConfig** | Business hours, working days, break times, booking rules |
| **CalendarIntegrationService** | Sync bookings to Google Calendar / Outlook |
| **LLMBookingAssistant** | AI-based intelligent time slot selection |
| **BirthdayEmailScheduler** | Daily automated birthday email job (APScheduler) |

## Key Features

**Multi-channel Support** - Email, Teams, WhatsApp, Calls, Facebook  
**Database Persistence** - PostgreSQL ORM (Booking, CalendarAccount tables)  
**AI Slot Selection** - LLM analyzes email preferences + customer history  
**Calendar Integration** - Google & Outlook with multi-account support  
**Birthday Automation** - Daily scheduled emails with timezone awareness  
**Conflict Detection** - Prevents double-booking across channels  
**Configurable Rules** - Business hours, break times, advance booking window, minimum notice  
**Cancellation Sync** - Removes events from calendar when booking cancelled  

## Quick Usage

```python
# Check availability
from scheduling.scheduler import check_availability
slots = check_availability(days_ahead=14)  # ["2026-04-03 09:00", ...]

# Book with AI slot selection
from scheduling.llm_booking_assistant import LLMBookingAssistant
assistant = LLMBookingAssistant()
slot, reasoning = assistant.select_best_appointment_slot(
    customer_email="user@example.com",
    email_content="I need service Tuesday afternoon",
    available_slots=slots
)

# Create booking
from scheduling.scheduler import book_slot
booking = book_slot(
    customer_email="user@example.com",
    slot=slot,
    channel="email",
    notes="Service type: Plumbing"
)

# Get customer history
from scheduling.scheduler import get_customer_bookings
bookings = get_customer_bookings("user@example.com")

# Cancel booking (auto-syncs to calendar)
from scheduling.scheduler import cancel_booking
cancel_booking(booking_id="BK20260402-143015", reason="Rescheduling")
```

## Configuration

Edit `scheduling_config.py`:
```python
working_days = [0,1,2,3,4]           # Mon-Fri (0=Mon, 4=Fri) - add 5,6 for weekends
business_hours_start = 9             # 9 AM
business_hours_end = 18              # 6 PM
slot_duration_minutes = 60           # 1-hour appointments
advance_booking_days = 14            # Allow 14-day advance booking
min_booking_notice_hours = 24        # Minimum 24-hour notice
break_times = [{"start": 12, "end": 13}]  # 12 PM - 1 PM lunch
```

Enable birthday scheduler in `main.py`:
```python
from scheduling.birthday_scheduler import BirthdayEmailScheduler
birthday_scheduler = BirthdayEmailScheduler(schedule_hour=12, schedule_minute=50)
birthday_scheduler.start()
app.state.birthday_scheduler = birthday_scheduler
```

## Data Model

**Booking** (PostgreSQL)
- `id`: BK20260402-143015 (auto-generated)
- `customer_email`, `slot`, `channel`: booking details
- `status`: confirmed/cancelled/completed/no-show
- `notes`, `created_at`, `reminder_sent`, `calendar_event_id`

**CalendarAccount** (Multi-provider support)
- `staff_id`, `provider` (google/outlook), `account_id`
- `access_token`, `refresh_token`, `token_expires_at`, `is_active`

## Integration with Channels

All channels use same interface:
```python
# Email, Teams, WhatsApp, etc. - same pattern
booking = book_slot(customer_id, slot, channel="email")
```

Bookings auto-sync to active calendar accounts when created/cancelled.
6. **Handle timezone issues** if supporting multiple timezones
7. **Test cancellation flow** to ensure consistency

## Troubleshooting

### No slots available
- Check if slots are within booking window (24 hours to 14 days)
- Verify working hours configuration
- Check if all slots are already booked
- Consider extending advance booking window

### Booking created but appears to fail
- Check bookings.jsonl file exists and is readable
- Verify slot was not already booked by another user
- Check system date/time is correct

### Past slots showing as available
- Verify system datetime is correct
- Check minimum booking notice is configured properly (should be at least 24 hours)
