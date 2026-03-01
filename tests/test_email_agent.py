from channels.email.email_agent import process_email


def test_email_pipeline():
    payload = {
        "from": "test@gmail.com",
        "subject": "Pricing",
        "body": "What is your emergency cost?"
    }

    result = process_email(payload)

    assert "intent" in result
    assert result["intent"] == "pricing_inquiry"
    assert "reply" in result
