"""Google Calendar provider implementation using existing Gmail OAuth credentials."""

import logging
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .base_provider import CalendarProvider, CalendarEvent
import config.config as cfg

logger = logging.getLogger(__name__)


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar provider supporting both token.json and OAuth token modes."""
    
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]
    
    def __init__(self, account_id: str = "primary", access_token: str = None,
                 refresh_token: str = None, token_expires_at: datetime = None):
        """Initialize Google Calendar provider.
        
        Supports two modes:
        1. token.json mode (preferred): Uses existing Gmail OAuth credentials with calendar scope
        2. OAuth token mode: Uses provided access/refresh tokens from database
        
        Args:
            account_id: Unique account identifier (default: primary)
            access_token: Token from database (optional, used if token.json not available)
            refresh_token: Refresh token from database (optional)
            token_expires_at: Token expiration (optional)
        """
        # Initialize parent with provided tokens (used as fallback)
        super().__init__(account_id, access_token or "", refresh_token, token_expires_at)
        self.service = None
        self._credentials = None
        self._use_token_json = False
        self._authenticate()
    
    def _get_credentials(self) -> Optional[Credentials]:
        """Load Google Credentials preferring token.json, fallback to provided tokens.
        
        Returns:
            Credentials object or None if unavailable
        """
        if self._credentials is not None:
            return self._credentials
        
        creds = None
        
        # Priority 1: Try to use token.json (Gmail already has it with calendar scope)
        if os.path.exists(cfg.GOOGLE_TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(
                    cfg.GOOGLE_TOKEN_FILE, self.SCOPES
                )
                self._use_token_json = True
                
                # Refresh if expired
                if creds.expired and creds.refresh_token:
                    logger.info("Google Calendar: Token from token.json expired, refreshing...")
                    try:
                        creds.refresh(Request())
                        self.access_token = creds.token
                        self.token_expires_at = creds.expiry
                        logger.info("✓ Google Calendar token refreshed from token.json")
                    except Exception as e:
                        logger.warning(f"Failed to refresh Calendar token: {e}")
                
                self._credentials = creds
                return creds
            except Exception as e:
                logger.debug(f"Could not load token.json: {e}")
                creds = None
        
        # Priority 2: Fallback to provided OAuth tokens from database
        if creds is None and self.access_token:
            try:
                logger.debug("Falling back to database OAuth tokens")
                creds = Credentials(
                    token=self.access_token,
                    refresh_token=self.refresh_token,
                    token_uri='https://oauth2.googleapis.com/token',
                    scopes=self.SCOPES
                )
                
                # Refresh if expired
                if creds.expired and creds.refresh_token:
                    logger.info("Google Calendar: Database token expired, refreshing...")
                    try:
                        creds.refresh(Request())
                        self.access_token = creds.token
                        self.token_expires_at = creds.expiry
                    except Exception as e:
                        logger.warning(f"Failed to refresh database token: {e}")
                
                self._credentials = creds
                return creds
            except Exception as e:
                logger.error(f"Failed to build credentials from database tokens: {e}")
                return None
        
        if creds is None:
            logger.error("No Google Calendar credentials available (no token.json or database tokens)")
            return None
        
        return creds
    
    def _authenticate(self):
        """Authenticate using token.json from Gmail setup."""
        self._get_credentials()
    
    def _get_service(self):
        """Get or create Google Calendar API service."""
        if self.service is None:
            creds = self._get_credentials()
            if creds:
                self.service = build('calendar', 'v3', credentials=creds)
        return self.service
    
    def authenticate(self) -> bool:
        """Verify Google Calendar API access.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            service = self._get_service()
            if not service:
                logger.error("Google Calendar service not available")
                return False
            
            # Test with a simple API call
            service.calendarList().list(maxResults=1).execute()
            logger.info(f"✓ Google Calendar authenticated for {self.account_id}")
            return True
        except HttpError as e:
            logger.error(f"Google Calendar authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Google Calendar authentication error: {e}")
            return False
    
    def refresh_access_token(self) -> Tuple[bool, Optional[str]]:
        """Refresh the Google OAuth access token.
        
        Returns:
            Tuple of (success: bool, new_token: Optional[str])
        """
        try:
            creds = self._get_credentials()
            if not creds or not creds.refresh_token:
                logger.error("No refresh token available")
                return False, None
            
            request = Request()
            creds.refresh(request)
            
            self.access_token = creds.token
            self.token_expires_at = creds.expiry
            
            logger.info(f"✓ Google Calendar token refreshed")
            return True, self.access_token
        except Exception as e:
            logger.error(f"Failed to refresh Google Calendar token: {e}")
            return False, None
    
    def get_events(self, calendar_id: str = 'primary', 
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   max_results: int = 100) -> List[CalendarEvent]:
        """Fetch calendar events.
        
        Args:
            calendar_id: Calendar ID (default: 'primary')
            start_time: Start of time range
            end_time: End of time range
            max_results: Maximum events to return
            
        Returns:
            List of CalendarEvent objects
        """
        try:
            if start_time is None:
                start_time = datetime.utcnow()
            if end_time is None:
                end_time = start_time + timedelta(days=30)
            
            service = self._get_service()
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = []
            for item in events_result.get('items', []):
                start = item['start'].get('dateTime', item['start'].get('date'))
                end = item['end'].get('dateTime', item['end'].get('date'))
                
                # Convert string to datetime if needed
                if isinstance(start, str) and 'T' not in start:
                    start = datetime.fromisoformat(start)
                else:
                    start = datetime.fromisoformat(start.replace('Z', '+00:00'))
                
                if isinstance(end, str) and 'T' not in end:
                    end = datetime.fromisoformat(end)
                else:
                    end = datetime.fromisoformat(end.replace('Z', '+00:00'))
                
                event = CalendarEvent(
                    event_id=item.get('id'),
                    title=item.get('summary', 'No Title'),
                    start_time=start,
                    end_time=end,
                    description=item.get('description'),
                    attendees=[a['email'] for a in item.get('attendees', [])]
                )
                events.append(event)
            
            logger.info(f"Retrieved {len(events)} events from Google Calendar")
            return events
        except HttpError as e:
            logger.error(f"Failed to retrieve events: {e}")
            return []
    
    def create_event(self, calendar_id: str, event: CalendarEvent) -> Tuple[bool, Optional[str]]:
        """Create a new Google Calendar event.
        
        Args:
            calendar_id: Calendar ID
            event: CalendarEvent object
            
        Returns:
            Tuple of (success: bool, event_id: Optional[str])
        """
        try:
            service = self._get_service()
            event_body = {
                'summary': event.title,
                'description': event.description,
                'start': {'dateTime': event.start_time.isoformat()},
                'end': {'dateTime': event.end_time.isoformat()},
            }
            
            if event.attendees:
                event_body['attendees'] = [{'email': email} for email in event.attendees]
            
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()
            
            logger.info(f"Created Google Calendar event: {created_event.get('id')}")
            return True, created_event.get('id')
        except HttpError as e:
            logger.error(f"Failed to create event: {e}")
            return False, None
    
    def update_event(self, calendar_id: str, event_id: str,
                     event: CalendarEvent) -> bool:
        """Update a Google Calendar event.
        
        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            event: Updated CalendarEvent object
            
        Returns:
            bool: True if update successful
        """
        try:
            service = self._get_service()
            event_body = {
                'summary': event.title,
                'description': event.description,
                'start': {'dateTime': event.start_time.isoformat()},
                'end': {'dateTime': event.end_time.isoformat()},
            }
            
            if event.attendees:
                event_body['attendees'] = [{'email': email} for email in event.attendees]
            
            service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event_body
            ).execute()
            
            logger.info(f"Updated Google Calendar event: {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Failed to update event: {e}")
            return False
    
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete a Google Calendar event.
        
        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            
        Returns:
            bool: True if deletion successful
        """
        try:
            service = self._get_service()
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Deleted Google Calendar event: {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Failed to delete event: {e}")
            return False
    
    def get_busy_slots(self, calendar_id: str = 'primary',
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> List[Tuple[datetime, datetime]]:
        """Get busy time slots from Google Calendar.
        
        Args:
            calendar_id: Calendar ID
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            List of (start, end) tuples for busy times
        """
        try:
            if start_time is None:
                start_time = datetime.utcnow()
            if end_time is None:
                end_time = start_time + timedelta(days=30)
            
            events = self.get_events(calendar_id, start_time, end_time, max_results=500)
            
            busy_slots = [
                (event.start_time, event.end_time)
                for event in events
                if event  # Filter out any None events
            ]
            
            logger.info(f"Found {len(busy_slots)} busy slots")
            return busy_slots
        except Exception as e:
            logger.error(f"Failed to get busy slots: {e}")
            return []
    
    def revoke_access(self) -> bool:
        """Revoke Google Calendar API access.
        
        Returns:
            bool: True if revocation successful
        """
        try:
            credentials = self._get_credentials()
            credentials.revoke(Request())
            logger.info(f"Revoked Google Calendar access for {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke access: {e}")
            return False
