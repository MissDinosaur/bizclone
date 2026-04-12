"""
Email sending with iCalendar attachments

Send booking confirmation emails with calendar invitations (.ics files)
Supports automatic recognition and import in Gmail, Outlook, and other email clients
"""

import logging
import base64
from datetime import datetime, timedelta
from typing import Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from channels.email.gmail_client import GmailClient
import config.config as cfg

logger = logging.getLogger(__name__)


class BookingEmailSender:
    """
    Send booking confirmation emails with iCalendar invitations
    
    Email structure:
    - Plain text version
    - HTML version
    - .ics file attachment (client will auto-recognize and add to calendar)
    """
    
    def __init__(self):
        self.gmail_client = GmailClient()
    
    def send_booking_confirmation_with_ics(
        self,
        customer_email: str,
        customer_name: str,
        appointment_slot: str,
        thread_id: str,
        message_id: str,
        original_subject: str = "",
        original_references: str = "",
        service_description: str = "Appointment",
        service_duration_minutes: int = 60,
        email_body: str = "",
        subject: str = "Your Booking is Confirmed"
    ) -> Tuple[bool, str]:
        """
        Send booking confirmation email with iCalendar invitation as thread reply
        
        Args:
            customer_email: Recipient email address
            customer_name: Recipient name
            appointment_slot: Appointment time in format '2026-04-03 14:00'
            thread_id: Gmail thread ID (for keeping conversation in same thread)
            message_id: Gmail message ID (for threading reference)
            service_description: Service description
            service_duration_minutes: Service duration in minutes
            email_body: Email body
            subject: Email subject (will be prefixed with "Re:" for threading)
            
        Returns:
            (success: bool, message_id: str | error_msg: str)
        """
        
        try:
            # OpenAI Fix: Use ORIGINAL subject (not custom subject)
            # Gmail threading algorithm requires subject consistency
            # This is #2 of the critical fixes for threading
            if original_subject:
                # Use original subject with "Re:" prefix only
                if original_subject.startswith("Re:"):
                    subject_with_prefix = original_subject
                else:
                    subject_with_prefix = f"Re: {original_subject}"
                logger.info(f"[ICS_EMAIL] Using original subject for threading: '{subject_with_prefix}'")
            else:
                # Fallback if no original subject (shouldn't happen)
                if not subject.startswith("Re: "):
                    subject_with_prefix = f"Re: {subject}"
                else:
                    subject_with_prefix = subject
                logger.warning(f"[ICS_EMAIL] No original subject provided, using fallback: '{subject_with_prefix}'")
            
            # Step 1: Generate iCalendar content
            ics_content = self._generate_ics(
                customer_email=customer_email,
                customer_name=customer_name,
                appointment_slot=appointment_slot,
                service_description=service_description,
                service_duration_minutes=service_duration_minutes
            )
            
            # Step 2: Build email with attachment
            message = self._build_email_with_ics_attachment(
                to_email=customer_email,
                to_name=customer_name,
                subject=subject_with_prefix,  # Use subject with "Re:" prefix for threading
                body=email_body,
                ics_content=ics_content
            )
            
            # Step 3: Send as threaded reply (keeps conversation in same thread with .ics attachment)
            # Pass original_references for complete conversation chain (OpenAI Fix #1)
            sent_message_id = self.gmail_client.send_email_reply_with_mime(
                to_email=customer_email,
                subject=subject_with_prefix,
                mime_message=message,
                thread_id=thread_id,
                message_id=message_id,
                original_references=original_references  # Critical: complete References chain
            )
            
            logger.info(f"Booking confirmation email with ICS sent to {customer_email} (thread: {thread_id})")
            return True, sent_message_id
            
        except Exception as e:
            logger.error(f"Failed to send booking confirmation email: {e}", exc_info=True)
            return False, str(e)
    
    def _generate_ics(
        self,
        customer_email: str,
        customer_name: str,
        appointment_slot: str,
        service_description: str,
        service_duration_minutes: int
    ) -> str:
        """
        Generate iCalendar format file content with explicit timezone info.
        
        CRITICAL FIX: Include TZID parameter in DTSTART/DTEND so calendar apps
        (Outlook, Gmail, Apple Calendar) interpret the time in the correct timezone.
        Without this, different calendar apps may show different times based on 
        the recipient's local timezone.
        
        This .ics file can be automatically recognized and imported by Gmail, Outlook, Apple Calendar, etc.
        Using METHOD:REQUEST indicates this is an invitation
        """
        
        try:
            # Parse appointment time
            start_dt = datetime.strptime(appointment_slot, "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=service_duration_minutes)
            
            # Generate unique UID (for calendar system deduplication)
            company_domain ='bizclone.com'
            uid = f"booking-{start_dt.timestamp()}-{customer_email}@{company_domain}"
            
            # Generate DTSTAMP (current UTC time)
            dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            
            # Timezone identifier - use global config to ensure consistency
            timezone_id = cfg.TIMEZONE
            
            # Build iCalendar content with proper TZID specification
            # CRITICAL: TZID parameter tells calendar apps to interpret timestamps in configured timezone
            # Includes both CET (winter, UTC+1) and CEST (summer, UTC+2) for Europe/Berlin
            ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//BizClone//Booking System//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VTIMEZONE
TZID:{timezone_id}
BEGIN:STANDARD
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART;TZID={timezone_id}:{start_dt.strftime('%Y%m%dT%H%M%S')}
DTEND;TZID={timezone_id}:{end_dt.strftime('%Y%m%dT%H%M%S')}
SUMMARY:{service_description}
DESCRIPTION:Booking Service: {service_description}\\nAppointment Time: {appointment_slot}\\nBooking Name: {customer_name}\\n\\nPlease confirm your availability. After receiving this invitation, your calendar system will automatically notify you.
LOCATION:Online
ORGANIZER;CN=BizClone Support:mailto:{cfg.COMPANY_EMAIL}
ATTENDEE;CN={customer_name};ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{customer_email}
STATUS:CONFIRMED
SEQUENCE:0
CREATED:{dtstamp}
LAST-MODIFIED:{dtstamp}
END:VEVENT
END:VCALENDAR"""
            
            return ics_content
            
        except Exception as e:
            logger.error(f"Failed to generate ICS: {e}", exc_info=True)
            return ""
    
    def _build_email_with_ics_attachment(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body: str,
        ics_content: str,
    ) -> MIMEMultipart:
        """
        Build email with:
        - Plain text email body
        - .ics file as attachment
        """
        
        # Create email container
        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From'] = cfg.COMPANY_EMAIL
        msg['To'] = to_email
        
        # Add plain text version only (no HTML)
        msg_text = MIMEText(body, 'plain', 'utf-8')
        msg.attach(msg_text)
        
        # Add .ics file as attachment
        # OpenAI Fix: Use application/ics NOT text/calendar (Gmail threading fix #3)
        # text/calendar triggers Gmail to treat as calendar event, breaking threading
        ics_attachment = MIMEBase('application', 'ics')
        ics_attachment.set_payload(ics_content)
        encoders.encode_base64(ics_attachment)
        ics_attachment.add_header(
            'Content-Disposition',
            'attachment',
            filename='appointment.ics'
        )
        # Additional header for Gmail recognition
        ics_attachment.add_header(
            'Content-Type',
            'application/ics; name="appointment.ics"'
        )
        msg.attach(ics_attachment)
        
        return msg


# Utility functions
_email_sender = None


def get_booking_email_sender() -> BookingEmailSender:
    """Get global BookingEmailSender singleton instance"""
    global _email_sender
    if _email_sender is None:
        _email_sender = BookingEmailSender()
    return _email_sender
