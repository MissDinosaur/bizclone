import os
import base64
import logging
from email.message import EmailMessage
from dotenv import load_dotenv

from googleapiclient.discovery import build
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
            if not os.path.exists(cfg.GMAIL_CREDENTIALS_FILE):
                logger.warning(
                    f"Gmail credentials.json not found at {cfg.GMAIL_CREDENTIALS_FILE}\n"
                    f"Email features will be unavailable. To enable:\n"
                    f"1. Download OAuth credentials from Google Cloud Console\n"
                    f"2. Save as {cfg.GMAIL_CREDENTIALS_FILE}\n"
                    f"3. Run authentication locally first, then copy token.json to container"
                )
                self.service = None
                return
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    cfg.GMAIL_CREDENTIALS_FILE, self.SCOPES
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

        sender = self._extract_header(headers, "From")
        subject = self._extract_header(headers, "Subject")
        message_id_header = self._extract_header(headers, "Message-ID")

        body = self._extract_body(message["payload"])

        return {
            "id": msg_id,
            "thread_id": message["threadId"],
            "message_id": message_id_header,
            "from": sender,
            "subject": subject,
            "body": body,
        }


    # -------------------------------
    # Helpers
    # -------------------------------
    def _extract_header(self, headers, name):
        """
        Extract specific header field.
        """
        for h in headers:
            if h["name"] == name:
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
        message["In-Reply-To"] = message_id
        message["References"] = message_id

        message.set_content(body)

        raw_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        self.service.users().messages().send(
            userId="me",
            body={
                "raw": raw_message,
                "threadId": thread_id
            }
        ).execute()

        return message
