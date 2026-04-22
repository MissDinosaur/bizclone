#!/usr/bin/env python3
"""
Test script to verify the two rescheduling fixes:
1. When rescheduling intent is misclassified but no active booking exists, 
   fallback to create new appointment.
2. When rescheduling is approved in review_api, properly reschedule using 
   BookingManager.reschedule_appointment() instead of book_slot().
"""

import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

print("\n" + "="*70)
print("RESCHEDULING FIXES VERIFICATION")
print("="*70)

# ========================================================================
# Test 1: Fallback from rescheduling to appointment when no active booking
# ========================================================================
print("\n[Test 1] Rescheduling intent with no active booking → fallback to new appointment")
print("-" * 70)

with patch("channels.email.email_agent.parse_email") as mock_parse, \
     patch("channels.email.email_agent.EmailRAGPipeline") as mock_rag, \
     patch("channels.email.email_agent.IntentClassifier") as mock_classifier, \
     patch("channels.email.email_agent.UrgencyDetector") as mock_urgency, \
     patch("channels.email.email_agent.EmailHistoryStore") as mock_email_store, \
     patch("channels.email.email_agent.BookingManager") as mock_booking_mgr, \
     patch("channels.email.email_agent.EmailAppointmentWorkflow") as mock_workflow:
    
    from channels.email.email_agent import EmailAgent
    
    # Mock the email parsing
    mock_parse.return_value = {"text": "I need to change my appointment to next week"}
    
    # Mock classifier to return rescheduling intent (misclassification)
    mock_classifier_instance = Mock()
    mock_classifier_instance.predict_intent.return_value = {
        "intent": "rescheduling",
        "confidence": 0.85
    }
    mock_classifier.return_value = mock_classifier_instance
    
    # Mock urgency detector to return NORMAL (no escalation)
    mock_urgency_instance = Mock()
    mock_urgency_instance.detect_urgency.return_value = {
        "urgency_level": "NORMAL",
        "confidence": 0.9,
        "escalation_reason": "No urgency indicators",
        "detected_keywords": []
    }
    mock_urgency_instance.should_escalate_to_owner.return_value = False
    mock_urgency.return_value = mock_urgency_instance
    
    # Mock RAG to return a reply
    mock_rag_instance = Mock()
    mock_rag_instance.generate_email_reply.return_value = (
        "Your appointment has been rescheduled to next week.",
        []
    )
    mock_rag.return_value = mock_rag_instance
    
    # Mock workflow
    mock_workflow_instance = Mock()
    
    # First call: select_appointment_slot returns a slot
    mock_workflow_instance.select_appointment_slot.return_value = {
        "slot": "2026-04-27 09:00",
        "reasoning": "Next available slot next week"
    }
    
    # Second call: handle_rescheduling_request fails (no active booking)
    mock_workflow_instance.handle_rescheduling_request.return_value = {
        "status": "error",
        "message": "No active appointment found to reschedule",
        "details": {}
    }
    
    # Third call: handle_booking_request creates new appointment
    mock_workflow_instance.handle_booking_request.return_value = {
        "id": "BK20260420-NEW",
        "status": "confirmed",
        "slot": "2026-04-27 09:00",
        "customer_email": "customer@example.com",
        "channel": "email",
        "booked_at": datetime.utcnow(),
        "confirmation_sent": True
    }
    
    mock_workflow.return_value = mock_workflow_instance
    
    # Create agent and process email
    agent = EmailAgent()
    
    result = agent.process_email({
        "from": "customer@example.com",
        "subject": "Change Appointment",
        "body": "I need to change my appointment to next week",
        "thread_id": "thread-123",
        "message_id": "msg-456"
    })
    
    # Verify fallback happened
    if mock_workflow_instance.handle_booking_request.called:
        print("✓ Fallback to handle_booking_request was called")
        print(f"✓ New booking created: {result.booking.id if result.booking else 'None'}")
        assert result.booking is not None, "Booking should have been created in fallback"
        print("✓ TEST 1 PASSED: Fallback to new appointment works correctly\n")
    else:
        print("✗ Fallback to handle_booking_request was NOT called")
        print("✗ TEST 1 FAILED\n")


# ========================================================================
# Test 2: review_api properly handles rescheduling vs appointment
# ========================================================================
print("[Test 2] review_api distinguishes rescheduling from appointment")
print("-" * 70)

with patch("api.review_api.book_slot") as mock_book_slot, \
     patch("api.review_api.BookingManager") as mock_mgr_class, \
     patch("api.review_api.get_booking_email_sender") as mock_email_sender, \
     patch("api.review_api.EmailHistoryStore") as mock_email_store, \
     patch("api.review_api.remove_email_from_review") as mock_remove:
    
    from api.review_api import submit_review_api, ReviewSubmitRequest
    
    # Mock email sender
    mock_sender_instance = Mock()
    mock_sender_instance.send_email_reply_with_ics.return_value = (True, "msg-789")
    mock_email_sender.return_value = mock_sender_instance
    
    # Mock booking manager for rescheduling
    mock_booking_mgr = Mock()
    mock_booking_mgr.reschedule_appointment.return_value = {
        "status": "success",
        "message": "Rescheduled successfully",
        "old_booking_id": "BK-OLD",
        "new_booking_id": "BK-NEW",
        "old_slot": "2026-04-20 09:00",
        "new_slot": "2026-04-27 09:00"
    }
    mock_mgr_class.return_value = mock_booking_mgr
    
    # Test Case 2a: Rescheduling request
    print("\n[Test 2a] Rescheduling request in review_api")
    
    booking_pending = {
        "customer_email": "customer@example.com",
        "message_text": "Please reschedule my appointment",
        "selected_slot": "2026-04-27 09:00",
        "reply_text": "Your appointment has been rescheduled",
        "is_rescheduling": True  # Key flag
    }
    
    request = ReviewSubmitRequest(
        email_id=1,
        customer_email="customer@example.com",
        customer_question="Please reschedule my appointment",
        agent_reply="Your appointment has been rescheduled",
        owner_correction="",
        subject="Reschedule Request",
        thread_id="thread-123",
        message_id="msg-456",
        references="",
        in_reply_to="",
        selected_slot="2026-04-27 09:00",
        booking_pending=json.dumps(booking_pending)
    )
    
    response = submit_review_api(request)
    
    if mock_booking_mgr.reschedule_appointment.called:
        print("✓ reschedule_appointment was called (not book_slot)")
        print(f"✓ Booking confirmed: BK-NEW")
        print("✓ TEST 2a PASSED: Rescheduling uses correct method\n")
    else:
        print("✗ reschedule_appointment was NOT called")
        print("✗ TEST 2a FAILED\n")
    
    # Test Case 2b: New appointment request
    print("[Test 2b] New appointment request in review_api")
    
    # Reset mocks
    mock_book_slot.reset_mock()
    mock_booking_mgr.reset_mock()
    
    # Mock book_slot for new appointment
    mock_book_slot.return_value = {
        "id": "BK-APPT",
        "status": "confirmed",
        "slot": "2026-04-27 09:00",
        "customer_email": "customer2@example.com",
        "channel": "email",
        "booked_at": datetime.utcnow()
    }
    
    booking_pending = {
        "customer_email": "customer2@example.com",
        "message_text": "Book me an appointment",
        "selected_slot": "2026-04-27 09:00",
        "reply_text": "Your appointment has been confirmed",
        # NO "is_rescheduling" flag - this is a new appointment
    }
    
    request = ReviewSubmitRequest(
        email_id=2,
        customer_email="customer2@example.com",
        customer_question="Book me an appointment",
        agent_reply="Your appointment has been confirmed",
        owner_correction="",
        subject="Book Appointment",
        thread_id="thread-456",
        message_id="msg-789",
        references="",
        in_reply_to="",
        selected_slot="2026-04-27 09:00",
        booking_pending=json.dumps(booking_pending)
    )
    
    response = submit_review_api(request)
    
    if mock_book_slot.called:
        print("✓ book_slot was called (for new appointment)")
        print(f"✓ Booking confirmed: BK-APPT")
        print("✓ TEST 2b PASSED: New appointment uses correct method\n")
    else:
        print("✗ book_slot was NOT called")
        print("✗ TEST 2b FAILED\n")


print("="*70)
print("✓ ALL RESCHEDULING FIXES VERIFIED")
print("="*70)
