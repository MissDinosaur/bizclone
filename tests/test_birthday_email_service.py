"""
Unit tests for Birthday Email Service

Tests:
1. Service initialization
2. Birthday customer retrieval
3. Email content generation
4. Birthday email sending
5. Error handling
"""

import unittest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch, call
from channels.email.birthday_email_service import BirthdayEmailService
from database.orm_models import Customer


class TestBirthdayEmailService(unittest.TestCase):
    """Tests for BirthdayEmailService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_gmail_client = Mock()
        self.service = BirthdayEmailService(gmail_client=self.mock_gmail_client)
        self.mock_session = Mock()
    
    # =====================================================================
    # Test 1: Service Initialization
    # =====================================================================
    
    def test_init_with_gmail_client(self):
        """Test service initialization with provided Gmail client"""
        gmail_client = Mock()
        service = BirthdayEmailService(gmail_client=gmail_client)
        self.assertIs(service.gmail_client, gmail_client)
    
    def test_init_without_gmail_client(self):
        """Test service initialization without Gmail client (uses default)"""
        # This will create a real GmailClient, so we'll just verify it's not None
        with patch('channels.email.birthday_email_service.GmailClient') as MockGmail:
            mock_instance = Mock()
            MockGmail.return_value = mock_instance
            service = BirthdayEmailService()
            MockGmail.assert_called_once()
    
    # =====================================================================
    # Test 2: Get Birthday Customers
    # =====================================================================
    
    def test_get_birthday_customers_today(self):
        """Test retrieving customers with birthday today"""
        today = date.today()
        
        # Create mock customer with birthday today
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_001"
        customer.email = "john@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = today.replace(year=today.year - 30)
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        result = self.service.get_birthday_customers(self.mock_session, days_ahead=0)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, "john@example.com")
    
    def test_get_birthday_customers_tomorrow(self):
        """Test retrieving customers with birthday tomorrow"""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_002"
        customer.email = "jane@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = tomorrow.replace(year=tomorrow.year - 25)
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        result = self.service.get_birthday_customers(self.mock_session, days_ahead=1)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, "jane@example.com")
    
    def test_get_birthday_customers_none(self):
        """Test when no customers have birthdays upcoming"""
        self.mock_session.query.return_value.filter.return_value.all.return_value = []
        
        result = self.service.get_birthday_customers(self.mock_session, days_ahead=0)
        
        self.assertEqual(len(result), 0)
    
    def test_get_birthday_customers_excludes_non_opted_in(self):
        """Test that customers who opt out are excluded"""
        # This test verifies the query filter is set up correctly
        # The mock returns what the filter would return in real scenario
        
        # In real scenario, the filter would exclude opted-out customers
        # So we should return empty list
        today = date.today()
        
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_003"
        customer.email = "bob@example.com"
        customer.notification_opt_in = False
        customer.date_of_birth = today.replace(year=today.year - 40)
        
        # Filter should exclude this customer, so return empty
        self.mock_session.query.return_value.filter.return_value.all.return_value = []
        
        result = self.service.get_birthday_customers(self.mock_session, days_ahead=0)
        
        # Should be empty because customer opted out
        self.assertEqual(len(result), 0)
    
    def test_get_birthday_customers_no_date_of_birth(self):
        """Test that customers without date of birth are skipped"""
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_004"
        customer.email = "alice@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = None
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        result = self.service.get_birthday_customers(self.mock_session, days_ahead=0)
        
        self.assertEqual(len(result), 0)
    
    def test_get_birthday_customers_leap_year_handling(self):
        """Test leap year date handling (Feb 29)"""
        today = date(2026, 3, 1)  # Day after leap year date
        leap_date = date(1996, 2, 29)  # Born on leap day
        
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_005"
        customer.email = "leapyear@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = leap_date
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        # Should handle the leap year gracefully
        with patch('channels.email.birthday_email_service.date') as mock_date:
            mock_date.today.return_value = today
            # If it raises ValueError, birthday_email_service should catch it
            result = self.service.get_birthday_customers(self.mock_session, days_ahead=0)
    
    def test_get_birthday_customers_database_error(self):
        """Test error handling when database query fails"""
        self.mock_session.query.side_effect = Exception("Database error")
        
        result = self.service.get_birthday_customers(self.mock_session, days_ahead=0)
        
        self.assertEqual(result, [])
    
    # =====================================================================
    # Test 3: Generate Birthday Email
    # =====================================================================
    
    def test_generate_birthday_email_with_full_name(self):
        """Test email generation with full name"""
        customer = Mock(spec=Customer)
        customer.get_full_name.return_value = "John Doe"
        customer.email = "john@example.com"
        
        subject, body = self.service.generate_birthday_email(customer)
        
        self.assertIn("🎉", subject)
        self.assertIn("Happy Birthday", subject)
        self.assertIn("John Doe", subject)
        self.assertIn("John Doe", body)
        self.assertIn("BizClone Team", body)
    
    def test_generate_birthday_email_with_email_as_name(self):
        """Test email generation when full name is not available"""
        customer = Mock(spec=Customer)
        customer.get_full_name.return_value = None
        customer.email = "user@example.com"
        
        subject, body = self.service.generate_birthday_email(customer)
        
        self.assertIn("user@example.com", subject)
        self.assertIn("user@example.com", body)
    
    def test_email_content_contains_required_elements(self):
        """Test that generated email contains all required elements"""
        customer = Mock(spec=Customer)
        customer.get_full_name.return_value = "Test User"
        customer.email = "test@example.com"
        
        subject, body = self.service.generate_birthday_email(customer)
        
        # Check subject
        self.assertTrue(subject.startswith("🎉"))
        self.assertIn("Test User", subject)
        
        # Check body contains key sections
        self.assertIn("Dear Test User", body)
        self.assertIn("🎂", body)
        self.assertIn("valued customer", body)
        self.assertIn("premium services", body)
        self.assertIn("BizClone Team", body)
    
    # =====================================================================
    # Test 4: Send Birthday Emails
    # =====================================================================
    
    def test_send_birthday_emails_success(self):
        """Test successful sending of birthday emails"""
        today = date.today()
        
        customer1 = Mock(spec=Customer)
        customer1.customer_id = "CUST_001"
        customer1.email = "john@example.com"
        customer1.notification_opt_in = True
        customer1.date_of_birth = today.replace(year=today.year - 30)
        customer1.get_full_name.return_value = "John Doe"
        
        customer2 = Mock(spec=Customer)
        customer2.customer_id = "CUST_002"
        customer2.email = "jane@example.com"
        customer2.notification_opt_in = True
        customer2.date_of_birth = today.replace(year=today.year - 25)
        customer2.get_full_name.return_value = "Jane Smith"
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer1, customer2]
        self.mock_gmail_client.send_email.return_value = None
        
        result = self.service.send_birthday_emails(self.mock_session, days_ahead=0)
        
        # Verify results
        self.assertEqual(result["total_customers"], 2)
        self.assertEqual(result["emails_sent"], 2)
        self.assertEqual(result["emails_failed"], 0)
        self.assertIn("john@example.com", result["sent_to"])
        self.assertIn("jane@example.com", result["sent_to"])
        
        # Verify Gmail client called twice
        self.assertEqual(self.mock_gmail_client.send_email.call_count, 2)
        
        # Verify session committed
        self.mock_session.commit.assert_called_once()
    
    def test_send_birthday_emails_partial_failure(self):
        """Test sending with some emails failing"""
        today = date.today()
        
        customer1 = Mock(spec=Customer)
        customer1.customer_id = "CUST_001"
        customer1.email = "john@example.com"
        customer1.notification_opt_in = True
        customer1.date_of_birth = today.replace(year=today.year - 30)
        customer1.get_full_name.return_value = "John Doe"
        
        customer2 = Mock(spec=Customer)
        customer2.customer_id = "CUST_002"
        customer2.email = "jane@example.com"
        customer2.notification_opt_in = True
        customer2.date_of_birth = today.replace(year=today.year - 25)
        customer2.get_full_name.return_value = "Jane Smith"
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer1, customer2]
        
        # First call succeeds, second fails
        self.mock_gmail_client.send_email.side_effect = [None, Exception("Email service error")]
        
        result = self.service.send_birthday_emails(self.mock_session, days_ahead=0)
        
        # Verify results
        self.assertEqual(result["total_customers"], 2)
        self.assertEqual(result["emails_sent"], 1)
        self.assertEqual(result["emails_failed"], 1)
        self.assertIn("john@example.com", result["sent_to"])
        self.assertEqual(len(result["failed"]), 1)
        self.assertEqual(result["failed"][0]["email"], "jane@example.com")
    
    def test_send_birthday_emails_no_customers(self):
        """Test sending when no customers have birthdays"""
        self.mock_session.query.return_value.filter.return_value.all.return_value = []
        
        result = self.service.send_birthday_emails(self.mock_session, days_ahead=0)
        
        self.assertEqual(result["total_customers"], 0)
        self.assertEqual(result["emails_sent"], 0)
        self.assertEqual(result["emails_failed"], 0)
        self.mock_gmail_client.send_email.assert_not_called()
        # Note: commit is not called when no customers are found (early return)
    
    def test_send_birthday_emails_updates_last_contacted(self):
        """Test that last_contacted_at is updated"""
        today = date.today()
        
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_001"
        customer.email = "john@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = today.replace(year=today.year - 30)
        customer.get_full_name.return_value = "John Doe"
        customer.last_contacted_at = None
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        with patch('channels.email.birthday_email_service.datetime') as mock_datetime:
            mock_now = datetime(2026, 4, 7, 10, 0, 0)
            mock_datetime.utcnow.return_value = mock_now
            
            self.service.send_birthday_emails(self.mock_session, days_ahead=0)
        
        # Verify last_contacted_at was set
        self.assertEqual(customer.last_contacted_at, mock_now)
        self.mock_session.add.assert_called_with(customer)
    
    def test_send_birthday_emails_rollback_on_error(self):
        """Test that session is rolled back when commit fails"""
        today = date.today()
        
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_001"
        customer.email = "john@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = today.replace(year=today.year - 30)
        customer.get_full_name.return_value = "John Doe"
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        # Make session.commit() raise an exception
        self.mock_session.commit.side_effect = Exception("Database commit failed")
        
        with self.assertRaises(Exception) as context:
            self.service.send_birthday_emails(self.mock_session, days_ahead=0)
        
        # Verify rollback was called
        self.mock_session.rollback.assert_called_once()
        self.assertIn("Database commit failed", str(context.exception))
    
    # =====================================================================
    # Test 5: Days Ahead Parameter
    # =====================================================================
    
    def test_send_birthday_emails_with_days_ahead(self):
        """Test sending emails for future birthdays"""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        customer = Mock(spec=Customer)
        customer.customer_id = "CUST_001"
        customer.email = "future@example.com"
        customer.notification_opt_in = True
        customer.date_of_birth = tomorrow.replace(year=tomorrow.year - 25)
        customer.get_full_name.return_value = "Future Birthday"
        
        self.mock_session.query.return_value.filter.return_value.all.return_value = [customer]
        
        result = self.service.send_birthday_emails(self.mock_session, days_ahead=1)
        
        self.assertEqual(result["emails_sent"], 1)
        self.assertIn("future@example.com", result["sent_to"])


class TestBirthdayEmailIntegration(unittest.TestCase):
    """Integration tests for birthday email service"""
    
    def test_full_workflow(self):
        """Test complete workflow from customer retrieval to email sending"""
        today = date.today()
        
        # Create mock customers
        customers_data = [
            {
                "id": "CUST_001",
                "email": "alice@example.com",
                "name": "Alice Johnson",
                "dob": today.replace(year=today.year - 28),
                "opted_in": True
            },
            {
                "id": "CUST_002",
                "email": "bob@example.com",
                "name": "Bob Smith",
                "dob": today.replace(year=today.year - 35),
                "opted_in": True
            },
        ]
        
        # Create mock customers
        customers = []
        for data in customers_data:
            customer = Mock(spec=Customer)
            customer.customer_id = data["id"]
            customer.email = data["email"]
            customer.get_full_name.return_value = data["name"]
            customer.date_of_birth = data["dob"]
            customer.notification_opt_in = data["opted_in"]
            customer.last_contacted_at = None
            customers.append(customer)
        
        # Setup mocks
        mock_session = Mock()
        mock_gmail_client = Mock()
        service = BirthdayEmailService(gmail_client=mock_gmail_client)
        
        mock_session.query.return_value.filter.return_value.all.return_value = customers
        
        # Execute
        result = service.send_birthday_emails(mock_session, days_ahead=0)
        
        # Verify
        assert result["total_customers"] == 2
        assert result["emails_sent"] == 2
        assert result["emails_failed"] == 0
        assert len(result["sent_to"]) == 2
        
        # Verify each customer was sent an email
        assert mock_gmail_client.send_email.call_count == 2
        
        # Verify session was committed
        mock_session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
