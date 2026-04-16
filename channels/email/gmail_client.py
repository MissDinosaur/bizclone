import os
import base64
import logging
import time
import socket
from email.message import EmailMessage
from dotenv import load_dotenv
from typing import List, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import config.config as cfg

logger = logging.getLogger(__name__)

load_dotenv()
ALLOWED_SENDERS = os.getenv("ALLOWED_SENDERS", "").split(",")

class GmailClient:
    """
    Gmail API Client for BizClone Email Agent.

    Supports:
    - OAuth authentication
    - Fetch unread emails
    - Parse sender/subject/body
    - Mark emails as read
    - Send email replies
    """

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    def __init__(self):
        self.service = None
        self._authenticate()

    # -------------------------------
    # Authentication
    # -------------------------------
    def _authenticate(self):
        """
        Authenticate Gmail API using:
        - credentials.json (OAuth app identity)
        - token.json (cached user permission)
        
        Features:
        - Automatically refresh expired tokens without browser (Docker-friendly)
        - Graceful fallback if credentials unavailable
        """

        creds = None

        # Load existing token if available
        if os.path.exists(cfg.GMAIL_TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(
                    cfg.GMAIL_TOKEN_FILE, self.SCOPES
                )
                
                # Check if token is expired but has refresh_token (works in Docker!)
                if creds.expired and creds.refresh_token:
                    logger.info("Gmail token expired, attempting to refresh...")
                    try:
                        creds.refresh(Request())
                        logger.info("✓ Gmail token refreshed successfully")
                        
                        # Try to save refreshed token (might fail if read-only filesystem in Docker)
                        try:
                            with open(cfg.GMAIL_TOKEN_FILE, "w") as token_file:
                                token_file.write(creds.to_json())
                            logger.debug("✓ Refreshed token saved to disk")
                        except (IOError, OSError) as save_err:
                            logger.debug(f"Could not save refreshed token (OK in Docker): {save_err}")
                            # Token is still valid in memory, that's what matters
                            
                    except Exception as refresh_err:
                        logger.warning(f"Failed to refresh Gmail token: {refresh_err}")
                        creds = None
                elif creds.valid:
                    logger.info("✓ Gmail authenticated with cached token")
                
            except Exception as e:
                logger.warning(f"Failed to load cached Gmail token: {e}")
                creds = None

        # If no valid cached token, try OAuth login only if credentials.json exists
        if not creds or not creds.valid:
            if not os.path.exists(cfg.GOOGLE_CREDENTIALS_FILE):
                logger.warning(
                    f"Gmail credentials.json not found at {cfg.GOOGLE_CREDENTIALS_FILE}\n"
                    f"Email features will be unavailable. To enable:\n"
                    f"1. Download OAuth credentials from Google Cloud Console\n"
                    f"2. Save as {cfg.GOOGLE_CREDENTIALS_FILE}\n"
                    f"3. Run authentication locally first, then copy token.json to container"
                )
                self.service = None
                return
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    cfg.GOOGLE_CREDENTIALS_FILE, self.SCOPES
                )
                # Try OAuth, but fail gracefully if no browser available (Docker)
                creds = flow.run_local_server(port=0)
                
                # Save token for future runs
                with open(cfg.GMAIL_TOKEN_FILE, "w") as token_file:
                    token_file.write(creds.to_json())
                logger.info("✓ Gmail authenticated with OAuth")
                
            except Exception as e:
                logger.warning(
                    f"Gmail OAuth authentication failed (expected in Docker without browser): {e}"
                )
                self.service = None
                return

        # Build Gmail service with valid credentials
        self.service = build("gmail", "v1", credentials=creds)

    # -------------------------------
    # Fetch Unread Emails
    # -------------------------------
    def fetch_unread_emails(self, max_results=10):
        """
        Fetch unread emails from Gmail inbox.
        Returns a list of parsed email payloads.
        """
        if not self.service:
            logger.warning("Gmail service not initialized. Cannot fetch emails.")
            return []
        
        results = (
            self.service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], q="is:unread", maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])

        emails = []
        for msg in messages:
            email_data = self._get_message(msg["id"])
            
            # Filter the Sender
            if email_data.get("from") and any(sender.lower() in email_data["from"].lower() for sender in ALLOWED_SENDERS):
                emails.append(email_data)

                # Mark as read after fetching
                self.mark_as_read(msg["id"])

        return emails

    # -------------------------------
    # Read Single Email
    # -------------------------------
    def _get_message(self, msg_id):
        """
        Retrieve full email content from Gmail.
        """
        if not self.service:
            logger.warning("Gmail service not initialized. Cannot retrieve message.")
            return {}
        
        message = (
            self.service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )

        headers = message["payload"]["headers"]

        # Debug: Log all header names to diagnose case-sensitivity issues
        header_names = [h["name"] for h in headers]
        logger.debug(f"DEBUG: Gmail API headers: {header_names}")

        sender = self._extract_header(headers, "From")
        subject = self._extract_header(headers, "Subject")
        message_id_header = self._extract_header(headers, "Message-ID")
        references = self._extract_header(headers, "References")  # CRITICAL: Extract full References chain
        in_reply_to = self._extract_header(headers, "In-Reply-To")  # Extract In-Reply-To for conversation context

        body = self._extract_body(message["payload"])
        
        if not sender:
            logger.warning(f"WARNING: Empty sender extracted from email msg_id={msg_id}")
            logger.warning(f"WARNING: Raw headers list: {headers}")
        

        return {
            "id": msg_id,
            "thread_id": message["threadId"],
            "message_id": message_id_header,
            "from": sender,
            "subject": subject,
            "body": body,
            "references": references,  # Store complete conversation chain
            "in_reply_to": in_reply_to,  # Store reply context
        }


    # -------------------------------
    # Helpers
    # -------------------------------
    def _extract_header(self, headers, name):
        """
        Extract specific header field.
        Uses case-insensitive matching to handle different email providers.
        Gmail may return headers with different casing for Outlook vs Gmail senders.
        """
        for h in headers:
            if h["name"].lower() == name.lower():
                return h["value"]
        return ""

    def _extract_body(self, payload):
        """
        Extract plain text email body.
        Handles multipart messages.
        """
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8")

        # Fallback if no parts
        data = payload["body"].get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")

        return ""

    # -------------------------------
    # Mark Email as Read
    # -------------------------------
    def mark_as_read(self, msg_id):
        """
        Remove UNREAD label from email.
        """
        if not self.service:
            logger.warning("Gmail service not initialized. Cannot mark email as read.")
            return
        
        self.service.users().messages().modify(
            userId="me",
            id=msg_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()

    # -------------------------------
    # Send Email Reply
    # -------------------------------
    def send_email_reply(self, to_email, subject, body, thread_id, message_id):
        """
        Send a threaded reply inside existing Gmail conversation.
        """
        if not self.service:
            logger.error("Gmail service not initialized. Cannot send email reply.")
            raise RuntimeError("Gmail service not configured. Please set up Gmail credentials.")
        
        message = EmailMessage()

        message["To"] = to_email
        message["Subject"] = "Re: " + subject
        
        # Ensure message_id has proper RFC 5322 format with angle brackets
        # Required format: <id@domain>
        if message_id:
            # Remove any existing angle brackets first
            message_id_formatted = message_id.strip('<>')
            # Add angle brackets in correct RFC format
            message_id_formatted = f"<{message_id_formatted}>"
        else:
            message_id_formatted = ""
        
        message["In-Reply-To"] = message_id_formatted
        message["References"] = message_id_formatted

        message.set_content(body)

        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        logger.debug(f"DEBUG: Sending email reply - thread_id='{thread_id}', message_id='{message_id}'")
        
        self.service.users().messages().send(
            userId="me",
            body={
                "raw": raw_message,
                "threadId": thread_id
            }
        ).execute()

        return message

    # -------------------------------
    # Send Email (New Message)
    # -------------------------------
    def send_email(self, to_email, subject, message):
        """
        Send a new email message (not a reply).
        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email message (string body or MIME object with headers)
            
        Returns:
            message_id: Gmail message ID
        """
        if not self.service:
            logger.error("Gmail service not initialized. Cannot send email.")
            raise RuntimeError("Gmail service not configured. Please set up Gmail credentials.")
        
        # Handle both string and MIME message types
        if isinstance(message, str):
            # Create EmailMessage from string
            email_msg = EmailMessage()
            email_msg["To"] = to_email
            email_msg["Subject"] = subject
            email_msg["From"] = cfg.COMPANY_EMAIL
            email_msg.set_content(message)
            message_bytes = email_msg.as_bytes()
        else:
            # Message is already a MIME object (MIMEMultipart, etc.)
            # Ensure it has proper headers if not already set
            if "To" not in message:
                message["To"] = to_email
            if "Subject" not in message:
                message["Subject"] = subject
            if "From" not in message:
                message["From"] = cfg.COMPANY_EMAIL
            message_bytes = message.as_bytes()
        
        # Encode and send
        raw_message = base64.urlsafe_b64encode(message_bytes).decode()
        
        result = self.service.users().messages().send(
            userId="me",
            body={"raw": raw_message}
        ).execute()
        
        message_id = result.get("id")
        logger.info(f"Email sent to {to_email} (ID: {message_id})")
        
        return message_id

    # -------------------------------
    # Send Email Reply with MIME (Supports Attachments)
    # -------------------------------
    def send_email_reply_with_mime(self, to_email, subject, mime_message, thread_id, message_id, original_references=""):
        """
        Send a threaded reply with MIME message (supports attachments like .ics files).
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            mime_message: MIME message object (MIMEMultipart) with all headers and attachments
            thread_id: Gmail thread ID (for keeping conversation in same thread)
            message_id: Gmail message ID (for threading reference)
            original_references: Complete original References header chain (required for Gmail threading)
            
        Returns:
            sent_message_id: Gmail message ID of sent reply
        """
        if not self.service:
            logger.error("Gmail service not initialized. Cannot send email reply.")
            raise RuntimeError("Gmail service not configured. Please set up Gmail credentials.")
        
        # Ensure message_id has proper RFC 5322 format with angle brackets
        # Required format: <id@domain>
        if message_id:
            # Remove any existing angle brackets first
            message_id_clean = message_id.strip('<>')
            # Add angle brackets in correct RFC format
            message_id_formatted = f"<{message_id_clean}>"
        else:
            message_id_formatted = None
            logger.warning("[THREADING] message_id is empty or None!")
        
        # Add threading headers to the existing MIME message
        # These are critical for Gmail to recognize this as a reply
        if message_id_formatted:
            mime_message["In-Reply-To"] = message_id_formatted
            
            # Gmail requires full conversation history, not just current message
            if original_references:
                full_references = f"{original_references} {message_id_formatted}"
            else:
                full_references = message_id_formatted
            
            mime_message["References"] = full_references
        else:
            logger.warning("[THREADING] Skipped setting threading headers - message_id_formatted is None")
        
        # Encode the complete MIME message with all attachments
        mime_bytes = mime_message.as_bytes()
        
        raw_message = base64.urlsafe_b64encode(mime_bytes).decode()
        
        # Send via Gmail API with thread reference
        result = self.service.users().messages().send(
            userId="me",
            body={
                "raw": raw_message,
                "threadId": thread_id
            }
        ).execute()
        
        sent_message_id = result.get("id")
        logger.info(f"Threaded reply sent to {to_email} (thread: {thread_id}, ID: {sent_message_id})")
        
        return sent_message_id
