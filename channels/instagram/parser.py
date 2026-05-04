"""
channels/instagram/parser.py

Parses raw Instagram DM message dicts into a normalised format
that the InstagramAgent can work with.
"""


def parse_instagram_message(raw_message: dict) -> dict:
    """
    Normalise a raw Instagram message dict.

    Input (from InstagramClient.fetch_unread_messages):
        {
            "sender_id":   "123456789",
            "sender_name": "John Doe",
            "text":        "Hello, do you have silk rugs?",
            "message_id":  "mid.xxx",
            "timestamp":   "2026-03-25T10:00:00+0000"
        }

    Output:
        {
            "from":       "123456789",
            "name":       "John Doe",
            "body":       "Hello, do you have silk rugs?",
            "message_id": "mid.xxx",
            "timestamp":  "2026-03-25T10:00:00+0000",
            "channel":    "instagram"
        }
    """
    return {
        "from": raw_message.get("sender_id", ""),
        "name": raw_message.get("sender_name", ""),
        "body": raw_message.get("text", ""),
        "message_id": raw_message.get("message_id", ""),
        "timestamp": raw_message.get("timestamp", ""),
        "channel": "instagram",
    }
