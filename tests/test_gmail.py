import pytest
from channels.email.gmail_client import GmailClient

client = GmailClient()

unread_emails = client.fetch_unread_emails(max_results=5)

for email in unread_emails:
    print("\n--- New Email ---")
    print("From:", email["from"])
    print("Subject:", email["subject"])
    print("Body:", email["body"])
