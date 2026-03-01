from channels.email.gmail_client import GmailClient

ALLOWED_SENDER = "@stud.srh-university.de"
client = GmailClient()

unread_emails = client.fetch_unread_emails(max_results=5)

        # Filter the Sender
filtered_emails = [
    email for email in unread_emails
    if email.get("from") and ALLOWED_SENDER.lower() in email["from"].lower()
]

if filtered_emails is None or filtered_emails == []:
    print(f"There is no unread emails from xxx{ALLOWED_SENDER}")

for email in filtered_emails:
    print("\n--- New Email ---")
    print("From:", email["from"])
    print("Subject:", email["subject"])
    print("Body:", email["body"])
