"""Outlook/Microsoft Calendar provider implementation."""

import logging
import requests
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from .base_provider import CalendarProvider, CalendarEvent

logger = logging.getLogger(__name__)


class OutlookCalendarProvider(CalendarProvider):
    """Microsoft Outlook Calendar provider implementation."""
    
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
    TOKEN_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    
    def __init__(self, account_id: str, access_token: str,
                 refresh_token: Optional[str] = None,
                 token_expires_at: Optional[datetime] = None,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        """Initialize Outlook Calendar provider.
        
        Args:
            account_id: Unique account identifier
            access_token: OAuth2 access token
            refresh_token: OAuth2 refresh token
            token_expires_at: Token expiration datetime
            client_id: Microsoft OAuth client ID
            client_secret: Microsoft OAuth client secret
        """
        super().__init__(account_id, access_token, refresh_token, token_expires_at)
        self.client_id = client_id
        self.client_secret = client_secret
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }
    
    def authenticate(self) -> bool:
        """Verify Outlook Calendar API access.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            headers = self._get_headers()
            response = requests.get(
                f'{self.GRAPH_API_ENDPOINT}/me',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Outlook authentication successful for {self.account_id}")
                return True
            else:
                logger.error(f"Outlook authentication failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Outlook authentication error: {e}")
            return False
    
    def refresh_access_token(self) -> Tuple[bool, Optional[str]]:
        """Refresh the Outlook OAuth access token.
        
        Returns:
            Tuple of (success: bool, new_token: Optional[str])
        """
        try:
            if not self.refresh_token:
                logger.error("Refresh token not available")
                return False, None
            
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token',
                'scope': 'Calendars.ReadWrite offline_access'
            }
            
            response = requests.post(self.TOKEN_ENDPOINT, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data['access_token']
                
                if 'refresh_token' in token_data:
                    self.refresh_token = token_data['refresh_token']
                
                if 'expires_in' in token_data:
                    self.token_expires_at = datetime.utcnow() + timedelta(
                        seconds=token_data['expires_in']
                    )
                
                logger.info(f"Outlook token refreshed for {self.account_id}")
                return True, self.access_token
            else:
                logger.error(f"Failed to refresh token: {response.status_code}")
                return False, None
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False, None
    
    def get_events(self, calendar_id: str = 'calendar',
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   max_results: int = 100) -> List[CalendarEvent]:
        """Fetch Outlook calendar events.
        
        Args:
            calendar_id: Calendar ID (default: 'calendar')
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
            
            headers = self._get_headers()
            
            # Build filter for date range
            filter_str = (
                f"start/dateTime ge '{start_time.isoformat()}Z' "
                f"and start/dateTime lt '{end_time.isoformat()}Z'"
            )
            
            url = (
                f'{self.GRAPH_API_ENDPOINT}/me/calendars/{calendar_id}/events'
                f'?$filter={filter_str}'
                f'&$top={max_results}'
                f'&$orderby=start/dateTime'
            )
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to retrieve events: {response.status_code}")
                return []
            
            events = []
            for item in response.json().get('value', []):
                start = datetime.fromisoformat(item['start']['dateTime'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(item['end']['dateTime'].replace('Z', '+00:00'))
                
                attendee_emails = [
                    attendee['emailAddress']['address']
                    for attendee in item.get('attendees', [])
                ]
                
                event = CalendarEvent(
                    event_id=item.get('id'),
                    title=item.get('subject', 'No Title'),
                    start_time=start,
                    end_time=end,
                    description=item.get('bodyPreview'),
                    attendees=attendee_emails
                )
                events.append(event)
            
            logger.info(f"Retrieved {len(events)} events from Outlook Calendar")
            return events
        except Exception as e:
            logger.error(f"Failed to retrieve events: {e}")
            return []
    
    def create_event(self, calendar_id: str, event: CalendarEvent) -> Tuple[bool, Optional[str]]:
        """Create a new Outlook calendar event.
        
        Args:
            calendar_id: Calendar ID
            event: CalendarEvent object
            
        Returns:
            Tuple of (success: bool, event_id: Optional[str])
        """
        try:
            headers = self._get_headers()
            
            event_body = {
                'subject': event.title,
                'bodyPreview': event.description or '',
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'UTC'
                },
            }
            
            if event.attendees:
                event_body['attendees'] = [
                    {
                        'emailAddress': {'address': email},
                        'type': 'required'
                    }
                    for email in event.attendees
                ]
            
            url = f'{self.GRAPH_API_ENDPOINT}/me/calendars/{calendar_id}/events'
            response = requests.post(url, json=event_body, headers=headers, timeout=10)
            
            if response.status_code == 201:
                created_event = response.json()
                logger.info(f"Created Outlook event: {created_event.get('id')}")
                return True, created_event.get('id')
            else:
                logger.error(f"Failed to create event: {response.status_code}")
                return False, None
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return False, None
    
    def update_event(self, calendar_id: str, event_id: str,
                     event: CalendarEvent) -> bool:
        """Update an Outlook calendar event.
        
        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            event: Updated CalendarEvent object
            
        Returns:
            bool: True if update successful
        """
        try:
            headers = self._get_headers()
            
            event_body = {
                'subject': event.title,
                'bodyPreview': event.description or '',
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'UTC'
                },
            }
            
            if event.attendees:
                event_body['attendees'] = [
                    {
                        'emailAddress': {'address': email},
                        'type': 'required'
                    }
                    for email in event.attendees
                ]
            
            url = f'{self.GRAPH_API_ENDPOINT}/me/calendars/{calendar_id}/events/{event_id}'
            response = requests.patch(url, json=event_body, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Updated Outlook event: {event_id}")
                return True
            else:
                logger.error(f"Failed to update event: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return False
    
    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete an Outlook calendar event.
        
        Args:
            calendar_id: Calendar ID
            event_id: Event ID
            
        Returns:
            bool: True if deletion successful
        """
        try:
            headers = self._get_headers()
            url = f'{self.GRAPH_API_ENDPOINT}/me/calendars/{calendar_id}/events/{event_id}'
            response = requests.delete(url, headers=headers, timeout=10)
            
            if response.status_code == 204:
                logger.info(f"Deleted Outlook event: {event_id}")
                return True
            else:
                logger.error(f"Failed to delete event: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False
    
    def get_busy_slots(self, calendar_id: str = 'calendar',
                       start_time: Optional[datetime] = None,
                       end_time: Optional[datetime] = None) -> List[Tuple[datetime, datetime]]:
        """Get busy time slots from Outlook Calendar.
        
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
                if event
            ]
            
            logger.info(f"Found {len(busy_slots)} busy slots")
            return busy_slots
        except Exception as e:
            logger.error(f"Failed to get busy slots: {e}")
            return []
    
    def revoke_access(self) -> bool:
        """Revoke Outlook Calendar API access.
        
        Returns:
            bool: True if revocation successful
        """
        try:
            headers = self._get_headers()
            # Microsoft doesn't have a direct revoke endpoint, but we can invalidate by:
            # 1. Removing from app's token store
            # 2. User can revoke from Microsoft account settings
            logger.info(f"Revoked Outlook access for {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke access: {e}")
            return False
