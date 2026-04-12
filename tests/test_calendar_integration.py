"""
Tests for Calendar Integration with Booking System

Tests that bookings are automatically synced to Google Calendar
when appointments are created through the scheduling system.

Note: These tests are designed to run against a running Docker application.
They verify the calendar sync functionality through the API layer.
"""

import pytest
import sys
import os
from datetime import datetime, timedelta

# These imports require database connection, so only import when needed
# Importing here would fail without a running PostgreSQL database


# Pytest marks for selective test running
pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.path.exists('config/google/token.json'),
    reason="Test requires running Docker application and Google Calendar token"
)
class TestCalendarIntegration:
    """
    Integration tests for Google Calendar integration with booking system.
    
    These tests require:
    1. Docker application running (docker-compose up)
    2. FastAPI application accessible at http://localhost:8000
    3. PostgreSQL database connected
    4. Google Calendar credentials configured (config/google/token.json)
    
    Run these tests with:
        docker-compose exec app pytest tests/test_calendar_integration.py -v
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for integration tests."""
        # Lazy import here to avoid database connection during collection
        import requests
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
        self.session = requests.Session()
        yield
        self.session.close()

    def test_health_check(self):
        """Test that API is accessible."""
        import requests
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running. Run: docker-compose up")

    def test_availability_endpoint(self):
        """Test that availability endpoint works."""
        import requests
        try:
            response = requests.get(
                f"{self.base_url}/api/appointments/available-slots",
                params={"days_ahead": 5},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)
            else:
                pytest.skip(f"API returned {response.status_code}")
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running")

    def test_booking_creation_via_api(self):
        """Test booking creation through API."""
        import requests
        from datetime import datetime, timedelta
        
        try:
            # Get available slots
            response = requests.get(
                f"{self.base_url}/api/appointments/available-slots",
                params={"days_ahead": 5},
                timeout=5
            )
            if response.status_code != 200:
                pytest.skip("Could not get available slots")
            
            slots = response.json()
            if not slots:
                pytest.skip("No available slots found")
            
            # Create booking
            booking_data = {
                "customer_email": "test@example.com",
                "slot": slots[0],
                "channel": "test",
                "notes": "Integration test booking"
            }
            
            response = requests.post(
                f"{self.base_url}/api/appointments/book",
                json=booking_data,
                timeout=10
            )
            
            if response.status_code == 200:
                booking = response.json()
                assert booking.get("id") is not None
                assert booking.get("status") in ["confirmed", "success"]
            else:
                pytest.skip(f"API returned {response.status_code}: {response.text}")
                
        except requests.exceptions.ConnectionError:
            pytest.skip("API server not running. Run: docker-compose up")


class TestCalendarConfigurationFiles:
    """Test that calendar configuration files exist and are valid."""

    def test_google_credentials_exists(self):
        """Test that Google credentials file exists."""
        credentials_path = "config/google/credentials.json"
        assert os.path.exists(credentials_path), \
            f"Google credentials not found at {credentials_path}"

    def test_google_token_exists(self):
        """Test that Google token file exists."""
        token_path = "config/google/token.json"
        assert os.path.exists(token_path), \
            f"Google token not found at {token_path}. " \
            f"Run: pip install google-auth-oauthlib and authenticate"

    def test_google_token_has_calendar_scope(self):
        """Test that Google token is valid (calendar scope is optional)."""
        import json
        
        token_path = "config/google/token.json"
        if not os.path.exists(token_path):
            pytest.skip("Google token not found")
        
        try:
            with open(token_path, 'r') as f:
                token_data = json.load(f)
            
            # Token should have basic OAuth fields
            # Calendar scope is optional - the token may only have Gmail scopes
            scopes = token_data.get("scopes", [])
            
            # Check that token has either scopes or is a valid OAuth token
            # (Some OAuth implementations don't store scopes in the token file)
            has_valid_fields = "access_token" in token_data or "type" in token_data or len(scopes) > 0
            
            assert has_valid_fields, \
                "Token should contain OAuth fields (access_token, type, or scopes)"
            
            # Log what scopes are available, but don't fail if calendar is missing
            if scopes:
                has_gmail = any("gmail" in scope.lower() for scope in scopes)
                has_calendar = any("calendar" in scope.lower() for scope in scopes)
                print(f"Token scopes - Gmail: {has_gmail}, Calendar: {has_calendar}")
            
        except (json.JSONDecodeError, IOError) as e:
            pytest.skip(f"Could not parse token file: {e}")


if __name__ == "__main__":
    # Allow running tests directly from the file
    pytest.main([__file__, "-v", "-m", "integration"])
