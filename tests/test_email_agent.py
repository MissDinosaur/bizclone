import pytest
from channels.email.email_agent import process_email
from config import config as cfg

def test_email_pipeline():
    payload = {
        "from": "test@gmail.com",
        "subject": "Pricing",
        "body": "What is your emergency cost?"
    }

    result = process_email(payload)

    assert "intent" in result
    assert result["intent"] in [
            cfg.PRICE_INQUERY,
            cfg.APPOINTMENT,
            cfg.CANCELLATION,
            cfg.WORKING_HOUR,
            cfg.EMERGENCY,
            cfg.FAQ
        ]
    assert "reply" in result
