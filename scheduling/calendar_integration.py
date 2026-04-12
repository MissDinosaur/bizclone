"""Calendar integration service for syncing bookings to calendar providers."""

import logging
from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from database.orm_models import CalendarAccount, Booking
from scheduling.calendar_providers import GoogleCalendarProvider, OutlookCalendarProvider
from scheduling.calendar_providers.base_provider import CalendarEvent

logger = logging.getLogger(__name__)

# Setup database
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


class CalendarIntegrationService:
    """Service to sync bookings to calendar providers."""
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize calendar integration service.
        
        Args:
            db_session: SQLAlchemy session (optional, creates new if not provided)
        """
        self.db = db_session or SessionLocal()
        self._owns_session = db_session is None
    
    def __del__(self):
        """Cleanup database session if we created it."""
        if self._owns_session and self.db:
            self.db.close()
    
    def _get_calendar_provider(self, staff_id: str) -> Optional[Tuple]:
        """Get active calendar provider for a staff member.
        
        Args:
            staff_id: Staff identifier
            
        Returns:
            Tuple of (provider_instance, account_id) or None
        """
        # Get active Google Calendar account (prefer Google over Outlook)
        account = self.db.query(CalendarAccount).filter(
            CalendarAccount.staff_id == staff_id,
            CalendarAccount.provider == 'google',
            CalendarAccount.is_active == True
        ).first()
        
        if not account:
            # Fallback to Outlook
            account = self.db.query(CalendarAccount).filter(
                CalendarAccount.staff_id == staff_id,
                CalendarAccount.provider == 'outlook',
                CalendarAccount.is_active == True
            ).first()
        
        if not account:
            logger.warning(f"No active calendar account found for staff {staff_id}")
            return None
        
        # Create provider instance
        if account.provider == 'google':
            provider = GoogleCalendarProvider(
                account_id=str(account.account_id),
                access_token=account.access_token,
                refresh_token=account.refresh_token,
                token_expires_at=account.token_expires_at
            )
        elif account.provider == 'outlook':
            provider = OutlookCalendarProvider(
                account_id=str(account.account_id),
                access_token=account.access_token,
                refresh_token=account.refresh_token,
                token_expires_at=account.token_expires_at
            )
        else:
            return None
        
        return provider, account.account_id
    
    def sync_booking_to_calendar(self, booking: Dict, staff_id: str = "default_staff",
                                default_duration: int = 60) -> Tuple[bool, Optional[str]]:
        """Sync a confirmed booking to calendar providers.
        
        Args:
            booking: Booking dictionary with keys: id, customer_email, slot, notes
            staff_id: Staff member handling the booking
            default_duration: Default appointment duration in minutes
            
        Returns:
            Tuple of (success: bool, event_id: Optional[str])
        """
        try:
            # Get calendar provider
            provider_info = self._get_calendar_provider(staff_id)
            if not provider_info:
                logger.info(f"No calendar provider for {staff_id}, skipping sync")
                return True, None  # Not an error, just not configured
            
            provider, account_id = provider_info
            
            # Refresh token if expired
            if provider.is_token_expired():
                success, _ = provider.refresh_access_token()
                if not success:
                    logger.error(f"Failed to refresh token for account {account_id}")
                    return False, None
                
                # Update token in database
                account = self.db.query(CalendarAccount).filter(
                    CalendarAccount.account_id == account_id
                ).first()
                if account:
                    account.access_token = provider.access_token
                    account.token_expires_at = provider.token_expires_at
                    self.db.commit()
            
            # Parse slot datetime
            if isinstance(booking['slot'], str):
                slot_dt = datetime.fromisoformat(booking['slot'])
            else:
                slot_dt = booking['slot']
            
            end_dt = slot_dt + timedelta(minutes=default_duration)
            
            # Create calendar event
            event = CalendarEvent(
                event_id=booking.get('id', ''),  # Use booking ID as event ID
                title=f"Appointment - {booking.get('customer_email', 'Customer')}",
                start_time=slot_dt,
                end_time=end_dt,
                description=booking.get('notes', f"Booking ID: {booking.get('id')}"),
                attendees=[booking.get('customer_email')] if booking.get('customer_email') else []
            )
            
            # Create event in calendar
            success, event_id = provider.create_event('primary', event)
            
            if success:
                logger.info(f"Booking {booking.get('id')} synced to calendar as event {event_id}")
                return True, event_id
            else:
                logger.error(f"Failed to create calendar event for booking {booking.get('id')}")
                return False, None
        
        except Exception as e:
            logger.error(f"Error syncing booking to calendar: {e}", exc_info=True)
            return False, None
    
    def sync_booking_cancellation(self, booking_id: str, staff_id: str = "default_staff") -> bool:
        """Sync booking cancellation to calendar providers.
        
        Args:
            booking_id: Booking identifier
            staff_id: Staff member handling the booking
            
        Returns:
            bool: True if successful or not configured
        """
        try:
            # Get calendar provider
            provider_info = self._get_calendar_provider(staff_id)
            if not provider_info:
                logger.info(f"No calendar provider for {staff_id}, skipping cancellation sync")
                return True
            
            provider, account_id = provider_info
            
            # Refresh token if expired
            if provider.is_token_expired():
                success, _ = provider.refresh_access_token()
                if not success:
                    logger.error(f"Failed to refresh token for account {account_id}")
                    return False
                
                # Update token in database
                account = self.db.query(CalendarAccount).filter(
                    CalendarAccount.account_id == account_id
                ).first()
                if account:
                    account.access_token = provider.access_token
                    account.token_expires_at = provider.token_expires_at
                    self.db.commit()
            
            # Delete event from calendar (using booking_id as event_id)
            success = provider.delete_event('primary', booking_id)
            
            if success:
                logger.info(f"Booking {booking_id} deleted from calendar")
                return True
            else:
                logger.warning(f"Failed to delete calendar event for booking {booking_id}")
                return False
        
        except Exception as e:
            logger.error(f"Error syncing booking cancellation: {e}", exc_info=True)
            return False


# Convenience functions for module-level access
_calendar_service = None


def get_calendar_integration_service(db: Optional[Session] = None) -> CalendarIntegrationService:
    """Get or create global calendar integration service.
    
    Args:
        db: Database session (optional)
        
    Returns:
        CalendarIntegrationService instance
    """
    global _calendar_service
    if _calendar_service is None:
        _calendar_service = CalendarIntegrationService(db)
    return _calendar_service


def sync_booking_to_calendar(booking: Dict, staff_id: str = "default_staff",
                            default_duration: int = 60) -> Tuple[bool, Optional[str]]:
    """Convenience function to sync booking to calendar.
    
    Args:
        booking: Booking dictionary
        staff_id: Staff identifier
        default_duration: Appointment duration in minutes
        
    Returns:
        Tuple of (success, event_id)
    """
    service = get_calendar_integration_service()
    return service.sync_booking_to_calendar(booking, staff_id, default_duration)


def sync_booking_cancellation(booking_id: str, staff_id: str = "default_staff") -> bool:
    """Convenience function to sync booking cancellation.
    
    Args:
        booking_id: Booking identifier
        staff_id: Staff identifier
        
    Returns:
        bool: True if successful
    """
    service = get_calendar_integration_service()
    return service.sync_booking_cancellation(booking_id, staff_id)
