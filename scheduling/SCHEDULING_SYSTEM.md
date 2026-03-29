# Scheduling System Documentation

## Overview

The scheduling system has been refactored from hard-coded slots to a flexible, database-backed appointment management system that can be used across all input channels (email, teams, whatsapp, call, facebook).

## Architecture

### Components

1. **SchedulingConfig** (`scheduling_config.py`)
   - Defines business hours, working days, break times
   - Generates available slots dynamically
   - Configurable parameters without code changes
   - Can be extended to load from database

2. **BookingStore** (`booking_store.py`)
   - Persists bookings to JSON file (`data/bookings/bookings.jsonl`)
   - Tracks booked, cancelled, and pending bookings
   - Generates unique booking IDs
   - Can be extended to use database backend

3. **AppointmentScheduler** (`scheduler.py`)
   - Central scheduling service used by all channels
   - Checks availability across booked slots
   - Creates and manages bookings
   - Provides convenience functions for backward compatibility

## Configuration

### Working Hours (Default)
- **Operating Days**: Monday - Friday
- **Business Hours**: 9 AM - 6 PM
- **Break Times**: 12 PM - 1 PM
- **Slot Duration**: 60 minutes

### Booking Rules (Default)
- **Advance Booking Window**: Up to 14 days in advance
- **Minimum Notice**: 24 hours required
- **Slot Format**: "YYYY-MM-DD HH:MM"

### Customizing Configuration

Edit `scheduling_config.py`:

```python
class SchedulingConfig:
    def __init__(self):
        self.business_hours_start = 9      # Change start hour
        self.business_hours_end = 18       # Change end hour
        self.slot_duration_minutes = 60    # Change slot duration
        self.min_booking_notice_hours = 24 # Change minimum notice
        self.advance_booking_days = 14     # Change max booking window
```

## Usage Examples

### Check Available Slots

```python
from scheduling.scheduler import check_availability

# Get slots for next 5 days (default)
slots = check_availability()

# Get slots for next 10 days
slots = check_availability(days_ahead=10)

# Returns: ["2026-03-05 09:00", "2026-03-05 10:00", ...]
```

### Book an Appointment

```python
from scheduling.scheduler import book_slot

booking = book_slot(
    customer_email="customer@example.com",
    slot="2026-03-05 10:00",
    channel="email",  # or "teams", "whatsapp", "call", "facebook"
    notes="Urgent plumbing issue"
)

# Returns:
# {
#     "id": "BK20260302140515000",
#     "status": "confirmed",
#     "customer_email": "customer@example.com",
#     "slot": "2026-03-05 10:00",
#     "channel": "email",
#     "booked_at": "2026-03-02T14:05:15.123456"
# }
```

### Get Customer Bookings

```python
from scheduling.scheduler import get_customer_bookings

bookings = get_customer_bookings("customer@example.com")

# Returns list of all bookings for that customer
```

### Cancel a Booking

```python
from scheduling.scheduler import cancel_booking

success = cancel_booking(
    booking_id="BK20260302140515000",
    reason="Customer requested cancellation"
)
```

## Integration with Channels

All channels use the same scheduling service for consistency:

### Email Agent (Already Integrated)
```python
# channels/email/email_agent.py
from scheduling.scheduler import check_availability, book_slot

if intent == cfg.APPOINTMENT:
    available_slots = check_availability(days_ahead=5)
    booking = book_slot(email_payload["from"], available_slots[0], channel="email")
```

### Teams Agent (Template Provided)
```python
# channels/teams/teams_agent.py
from scheduling.scheduler import check_availability, book_slot

booking = book_slot(user_email, slot, channel="teams")
```

### WhatsApp Agent (Template Provided)
```python
# channels/whatsapp/whatsapp_agent.py
booking = book_slot(user_phone, slot, channel="whatsapp")
```

### Call Agent (Template Provided)
```python
# channels/call/call_agent.py
booking = book_slot(caller_phone, slot, channel="call")
```

### Facebook Agent (Template Provided)
```python
# channels/facebook/facebook_agent.py
booking = book_slot(user_facebook_id, slot, channel="facebook")
```

## Data Storage

### Bookings File Structure

Each booking is stored as a JSONL line in `data/bookings/bookings.jsonl`:

```json
{
  "id": "BK20260302140515000",
  "customer_email": "customer@example.com",
  "slot": "2026-03-05 10:00",
  "channel": "email",
  "notes": "Customer requested appointment",
  "status": "confirmed",
  "booked_at": "2026-03-02T14:05:15.123456",
  "reminder_sent": false
}
```

### Booking Statuses
- `confirmed`: Successfully booked
- `cancelled`: Cancelled after booking
- `completed`: Appointment completed
- `no-show`: Customer didn't show up

## Future Enhancements

1. **Database Backend**: Replace JSON file with PostgreSQL/MongoDB
2. **Calendar Integration**: Sync with Google Calendar, Outlook
3. **Reminders**: Automated booking reminders via email/SMS
4. **Conflicts**: Handle double-booking across channels
5. **Dynamic Availability**: Load availability from separate calendar system
6. **Cancellation Policies**: Auto-cancel bookings per policy
7. **Rescheduling**: Allow customers to reschedule bookings
8. **Buffer Times**: Add buffer between appointments
9. **Resource Allocation**: Support multiple technicians/resources
10. **Recurring Appointments**: Support repeating bookings

## Best Practices

1. **Always check availability first** before attempting to book
2. **Provide feedback** to user if booking fails
3. **Store booking ID** for cancellation/rescheduling
4. **Use channel identifier** in booking for tracking
5. **Add descriptive notes** about booking source
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
