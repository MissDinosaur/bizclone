"""Abstract base class for calendar provider implementations."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class CalendarEvent:
    """Represents a calendar event."""
    
    def __init__(self, event_id: str, title: str, start_time: datetime, 
                 end_time: datetime, description: Optional[str] = None,
                 attendees: Optional[List[str]] = None):
        self.event_id = event_id
        self.title = title
        self.start_time = start_time
        self.end_time = end_time
        self.description = description
        self.attendees = attendees or []
    
    def to_dict(self) -> Dict:
        return {
            'event_id': self.event_id,
            'title': self.title,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'description': self.description,
            'attendees': self.attendees,
        }


class CalendarProvider(ABC):
    """Abstract base class for calendar providers (Google, Outlook, etc.)."""
    
    def __init__(self, account_id: str, access_token: str, 
                 refresh_token: Optional[str] = None,
                 token_expires_at: Optional[datetime] = None):
        """Initialize calendar provider.
        
        Args:
            account_id: Unique account identifier
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            token_expires_at: Token expiration datetime
        """
        self.account_id = account_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Verify credentials are valid.
        
        Returns:
            bool: True if authentication successful
        """
        pass
    
    @abstractmethod
    def refresh_access_token(self) -> Tuple[bool, Optional[str]]:
        """Refresh the access token using refresh token.
        
        Returns:
            Tuple of (success: bool, new_token: Optional[str])
        """
        pass
    
    @abstractmethod
    def get_events(self, calendar_id: str, start_time: datetime, 
                   end_time: datetime, max_results: int = 100) -> List[CalendarEvent]:
        """Fetch calendar events in the specified time range.
        
        Args:
            calendar_id: Calendar identifier
            start_time: Start of time range
            end_time: End of time range
            max_results: Maximum number of events to return
            
        Returns:
            List of CalendarEvent objects
        """
        pass
    
    @abstractmethod
    def create_event(self, calendar_id: str, event: CalendarEvent) -> Tuple[bool, Optional[str]]:
        """Create a new calendar event.
        
        Args:
            calendar_id: Calendar identifier
            event: CalendarEvent object
            
        Returns:
            Tuple of (success: bool, event_id: Optional[str])
        """
        pass
    
    @abstractmethod
    def update_event(self, calendar_id: str, event_id: str, 
                     event: CalendarEvent) -> bool:
        """Update an existing calendar event.
        
        Args:
            calendar_id: Calendar identifier
            event_id: Event identifier
            event: Updated CalendarEvent object
            
        Returns:
            bool: True if update successful
        """
        pass
    
    @abstractmethod
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete a calendar event.
        
        Args:
            calendar_id: Calendar identifier
            event_id: Event identifier
            
        Returns:
            bool: True if deletion successful
        """
        pass
    
    @abstractmethod
    def get_busy_slots(self, calendar_id: str, start_time: datetime, 
                       end_time: datetime) -> List[Tuple[datetime, datetime]]:
        """Get busy time slots for the calendar.
        
        Args:
            calendar_id: Calendar identifier
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of (start_time, end_time) tuples for busy slots
        """
        pass
    
    @abstractmethod
    def revoke_access(self) -> bool:
        """Revoke the OAuth access token.
        
        Returns:
            bool: True if revocation successful
        """
        pass
    
    def is_token_expired(self) -> bool:
        """Check if access token is expired.
        
        Returns:
            bool: True if token is expired or expiration time unknown
        """
        if not self.token_expires_at:
            return False
        return datetime.utcnow() >= self.token_expires_at
