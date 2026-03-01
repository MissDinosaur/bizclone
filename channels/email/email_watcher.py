import time
import threading

from channels.email.gmail_client import GmailClient
from channels.email.email_agent import process_email
from channels.email.review_store import save_review_context

POLL_INTERVAL = 60 # 1 minute #300

class EmailWatcher:
    """
    Background Email Polling Service.

    Every N seconds:
    - fetch unread emails
    - run Email Agent pipeline
    - send automated reply
    """

    def __init__(self, poll_interval=POLL_INTERVAL):
        self.poll_interval = poll_interval
        self.gmail = GmailClient()
        self.running = False

    def start(self):
        """
        Start watcher in a separate daemon thread.
        """
        if self.running:
            return

        self.running = True
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

        print("EmailWatcher started in background...")

    def _run_loop(self):
        """
        Main polling loop.
        """
        while self.running:
            print("Checking Gmail inbox for new unread emails...")

            try:
                unread_emails = self.gmail.fetch_unread_emails()

                if unread_emails:
                    print(f"Found {len(unread_emails)} new email(s).")

                    for email in unread_emails:
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
                                # "intent": result["intent"],
                                # "kb_field": "pricing"
                            })

                            print("Review available at: http://localhost:8000/review")

                            continue

                        # Case 2: Auto-send normal email
                        # Auto-reply back to sender
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

                else:
                    print("No new emails.")

            except Exception as e:
                print("EmailWatcher Error:", str(e))

            # Wait specific minutes
            time.sleep(self.poll_interval)


    def stop(self):
        """
        Stop watcher gracefully.
        """
        self.running = False
        print("EmailWatcher stopped.")
