from channels.base_watcher import BaseChannelWatcher
from channels.email.gmail_client import GmailClient
from channels.email.email_agent import process_email
from channels.email.review_store import save_review_context


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
        Args:
            email: Email dictionary with keys: from, subject, body, thread_id, message_id
        """
        print("Processing email from:", email["from"])

        # Run BizClone Email Agent pipeline
        result = process_email(email)
        print("Customer email has been parsed.")

        # Case 1: Emergency → Block and require review
        if result["status"] == "needs_review":
            print("Emergency email detected. Awaiting owner review...")
            save_review_context({
                "customer_email": email["from"],
                "customer_question": result["customer_question"],
                "agent_reply": result["reply"],
                "subject": email["subject"],
                "thread_id": email["thread_id"],
                "message_id": email["message_id"]
            })
            print("Review available at: http://localhost:8000/review")
            return

        # Case 2: Auto-send normal email
        if result["status"] == "auto_send":
            print("Not Emergency email. Will send email reply directly")
            self.gmail.send_email_reply(
                to_email=email["from"],
                subject=email["subject"],
                body=result["reply"],
                thread_id=email["thread_id"],
                message_id=email["message_id"]
            )
            print("Reply sent successfully.")
