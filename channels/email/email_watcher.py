import logging
from channels.base_watcher import BaseChannelWatcher
from channels.email.gmail_client import GmailClient
from channels.email.email_agent import process_email
from channels.email.review_store import save_review_context

logger = logging.getLogger(__name__)


class EmailWatcher(BaseChannelWatcher):
    """
    Background Email Polling Service.
    Every N seconds:
    - fetch unread emails
    - run Email Agent pipeline
    - send automated reply or hold for review
    """

    def __init__(self, poll_interval=300):
        super().__init__(channel_name="email", poll_interval=poll_interval)
        self.gmail = GmailClient()

    def fetch_unread_messages(self):
        """
        Fetch unread emails from Gmail.
        Returns:
            List of email dictionaries
        """
        return self.gmail.fetch_unread_emails()

    def process_message(self, email):
        """
        Process a single email through the Email Agent pipeline.
        
        Decision Logic (based on urgency, not intent):
        - CRITICAL urgency → always escalate to owner
        - HIGH urgency → escalate to owner
        - NORMAL urgency → auto-send with LLM response
        
        Args:
            email: Email dictionary with keys: from, subject, body, thread_id, message_id
        """
        logger.info(f"email - processing message from {email['from']}")

        # Run BizClone Email Agent pipeline (with separated intent + urgency detection)
        result = process_email(email)

        # Extract urgency info from metadata if available
        urgency_level = result.metadata.get("urgency_level", "UNKNOWN") if result.metadata else "UNKNOWN"
        escalation_reason = result.metadata.get("escalation_reason", "") if result.metadata else ""
        detected_keywords = result.metadata.get("detected_keywords", []) if result.metadata else []

        # Case 1: Urgent email → Block and require owner review
        if result.status == "needs_review":
            logger.warning(
                f"email - [{urgency_level}] requires review from {email['from']}",
                extra={"channel": "email"}
            )
            logger.warning(f"email - Reason: {escalation_reason}", extra={"channel": "email"})
            if detected_keywords:
                logger.warning(f"email - Keywords: {detected_keywords}", extra={"channel": "email"})

            save_review_context({
                "customer_email": email["from"],
                "customer_question": email["body"],
                "agent_reply": result.reply,
                "subject": email["subject"],
                "thread_id": email["thread_id"],
                "message_id": email["message_id"],
                "intent": result.intent.value,
                "urgency_level": urgency_level,
                "escalation_reason": escalation_reason,
                "detected_keywords": detected_keywords
            })

            logger.info(f"email - Owner action required: http://localhost:8000/review")
            return

        # Case 2: Normal email → Auto-send LLM response
        if result.status == "auto_send":
            logger.info(f"email - Auto-sending reply (urgency: {urgency_level})", extra={"channel": "email"})
            try:
                self.gmail.send_email_reply(
                    to_email=email["from"],
                    subject=email["subject"],
                    body=result.reply,
                    thread_id=email["thread_id"],
                    message_id=email["message_id"]
                )
                logger.info(f"email - ✓ Reply sent to {email['from']}", extra={"channel": "email"})
                
                # Log booking if applicable
                if result.booking:
                    logger.info(f"email - Booking created: {result.booking.id}", extra={"channel": "email"})
            
            except RuntimeError as e:
                logger.error(f"email - ✗ Cannot send email: {str(e)}", extra={"channel": "email"})
                logger.warning(
                    f"email - Gmail not configured. Falling back to owner review.",
                    extra={"channel": "email"}
                )
                # Escalate to owner for manual handling
                save_review_context({
                    "customer_email": email["from"],
                    "customer_question": email["body"],
                    "agent_reply": result.reply,
                    "subject": email["subject"],
                    "escalation_reason": f"Gmail send error: {str(e)}"
                })
