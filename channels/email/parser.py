def parse_email(email_payload: dict) -> str:
    """
    Extract and normalize the content of an incoming email.
    """
    subject = email_payload.get("subject", "")
    body = email_payload.get("body", "")

    normalized = f"{subject}\n{body}".strip()
    return {
        "channel": "email",
        "sender": email_payload.get("from", ""),
        "text": normalized
    }
