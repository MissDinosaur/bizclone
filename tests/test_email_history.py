"""
Test file for Email History Store and Context-Aware RAG Pipeline.

This demonstrates the new email history feature that:
1. Stores incoming emails in SQLite
2. Retrieves conversation history for LLM context
3. Enhances email replies with previous interaction context
"""

import logging
from datetime import datetime
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_email_history_store():
    """Test the EmailHistoryStore functionality."""
    print("\n" + "="*70)
    print("TEST 1: Email History Store - Save and Retrieve")
    print("="*70)
    
    from knowledge_base.email_history_store import EmailHistoryStore
    
    # Use temporary database for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_bizclone.db")
        store = EmailHistoryStore(db_path=db_path)
        
        # Test 1: Save incoming customer email
        print("\n1. Saving incoming customer email...")
        success = store.save_email(
            customer_email="john.smith@example.com",
            sender_category="customer",
            subject="About your plumbing services",
            body="Hi, I have a leaking pipe in my bathroom. Can you help?",
            intent="general_faq_question",
            channel="email"
        )
        assert success, "Failed to save incoming email"
        print("   ✓ Incoming email saved")
        
        # Test 2: Save support's reply
        print("\n2. Saving support reply...")
        success = store.save_email(
            customer_email="john.smith@example.com",
            sender_category="support",
            subject="Re: About your plumbing services",
            body="Thank you for contacting us! We specialize in pipe repairs. Can you describe the leak?",
            our_reply="Thank you for contacting us! We specialize in pipe repairs. Can you describe the leak?",
            intent="general_faq_question",
            channel="email"
        )
        assert success, "Failed to save support reply"
        print("   ✓ Support reply saved")
        
        # Test 3: Save additional emails
        print("\n3. Saving more customer interactions...")
        store.save_email(
            customer_email="john.smith@example.com",
            sender_category="customer",
            subject="Leak is getting worse",
            body="The leak is getting worse. Can you come by tomorrow?",
            intent="appointment_booking_request",
            channel="email"
        )
        store.save_email(
            customer_email="john.smith@example.com",
            sender_category="support",
            subject="Re: Leak is getting worse",
            body="We can schedule you for tomorrow at 2 PM. Is that works for you?",
            our_reply="We can schedule you for tomorrow at 2 PM. Is that works for you?",
            intent="appointment_booking_request",
            channel="email"
        )
        print("   ✓ Additional emails saved")
        
        # Test 4: Retrieve conversation history
        print("\n4. Retrieving conversation history...")
        history = store.get_customer_history("john.smith@example.com", limit=5)
        assert len(history) > 0, "No history retrieved"
        print(f"   ✓ Retrieved {len(history)} emails from history")
        
        print("\n   Conversation History:")
        print("   " + "-"*60)
        for i, email in enumerate(history, 1):
            print(f"\n   Email {i}:")
            print(f"      Timestamp: {email['timestamp']}")
            print(f"      From: {email['sender'].upper()}")
            print(f"      Subject: {email['subject']}")
            print(f"      Intent: {email['intent']}")
            preview = email['body'][:50] + "..." if len(email['body']) > 50 else email['body']
            print(f"      Body: {preview}")
        
        # Test 5: Get formatted prompt context
        print("\n5. Getting formatted conversation for LLM prompt...")
        prompt_context = store.get_conversation_for_prompt("john.smith@example.com", limit=3)
        assert "john.smith@example.com" in prompt_context or "CUSTOMER" in prompt_context
        print("   ✓ Formatted context generated")
        print("\n   Prompt Context:")
        print("   " + "-"*60)
        print(prompt_context)
        
        # Test 6: Database statistics
        print("\n6. Getting database statistics...")
        stats = store.get_database_stats()
        print(f"   ✓ Total emails stored: {stats['total_emails']}")
        print(f"   ✓ Unique customers: {stats['unique_customers']}")
        
        # Test 7: Different customer
        print("\n7. Testing multiple customers...")
        store.save_email(
            customer_email="jane.doe@example.com",
            sender_category="customer",
            subject="Service inquiry",
            body="What's your hourly rate?",
            intent="pricing_inquiry",
            channel="email"
        )
        stats = store.get_database_stats()
        assert stats['unique_customers'] >= 2, "Multiple customers not recorded"
        print(f"   ✓ Now tracking {stats['unique_customers']} unique customers")



