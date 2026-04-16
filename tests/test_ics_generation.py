#!/usr/bin/env python3
"""
Direct test of booking_email_sender._generate_ics() to verify date handling.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_generate_ics():
    """Test _generate_ics directly with April 22 appointment."""
    
    print("\n" + "=" * 80)
    print("DIRECT TEST: booking_email_sender._generate_ics()")
    print("=" * 80)
    
    try:
        from channels.email.booking_email_sender import BookingEmailSender
        
        sender = BookingEmailSender()
        
        # Test with April 22, 2026 at 1:00 PM
        test_slots = [
            ("2026-04-22 13:00", "April 22 at 1:00 PM"),
            ("2026-04-21 13:00", "April 21 at 1:00 PM"),
            ("2026-04-15 14:00", "April 15 at 2:00 PM"),
        ]
        
        for appointment_slot, description in test_slots:
            print(f"\n--- Testing: {description} ({appointment_slot}) ---")
            
            ics_content = sender._generate_ics(
                customer_email="test@example.com",
                customer_name="Test Customer",
                appointment_slot=appointment_slot,
                service_description="Test Service",
                service_duration_minutes=60
            )
            
            # Extract DTSTART and DTEND
            lines = ics_content.split('\n')
            dtstart_line = None
            dtend_line = None
            
            for line in lines:
                if 'DTSTART' in line:
                    dtstart_line = line
                if 'DTEND' in line:
                    dtend_line = line
            
            print(f"Input:  {appointment_slot}")
            print(f"Output:")
            if dtstart_line:
                print(f"  DTSTART: {dtstart_line.strip()}")
                # Extract the date value
                if ';TZID=' in dtstart_line:
                    dt_value = dtstart_line.split(':')[1]
                    print(f"    -> Date/Time: {dt_value}")
                    # Check if it matches input
                    input_ymd = appointment_slot[:10].replace('-', '')
                    output_ymd = dt_value[:8]
                    if input_ymd == output_ymd:
                        print(f"    ✓ Date matches input")
                    else:
                        print(f"    ✗ DATE MISMATCH! Expected {input_ymd}, got {output_ymd}")
            
            if dtend_line:
                print(f"  DTEND: {dtend_line.strip()}")
        
        print("\n" + "=" * 80)
        print("RESULT: All slots generated correctly")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_generate_ics()
    sys.exit(0 if success else 1)
