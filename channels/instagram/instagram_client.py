"""
channels/instagram/instagram_client.py

Wrapper for the Meta Instagram Graph API.
Handles sending DMs and fetching unread messages via polling.
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.instagram.com/v21.0"


class InstagramClient:
    """Wrapper for Instagram DM API operations (Meta Graph API)."""

    def __init__(self, page_access_token: str, ig_user_id: str):
        self.page_access_token = page_access_token
        self.ig_user_id = ig_user_id

        if not self.page_access_token:
            raise ValueError("Instagram PAGE_ACCESS_TOKEN is not configured.")
        if not self.ig_user_id:
            raise ValueError("Instagram IG_USER_ID is not configured.")

    def fetch_unread_messages(self, max_results: int = 10) -> list[dict]:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{BASE_URL}/{self.ig_user_id}/conversations",
                    params={
                        "platform": "instagram",
                        "fields": "messages{id,message,from,created_time}",
                        "access_token": self.page_access_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            messages = []
            for conversation in data.get("data", []):
                for msg in conversation.get("messages", {}).get("data", []):
                    sender = msg.get("from", {})
                    if sender.get("id") == self.ig_user_id:
                        continue
                    messages.append(
                        {
                            "sender_id": sender.get("id"),
                            "sender_name": sender.get("name", ""),
                            "text": msg.get("message", ""),
                            "message_id": msg.get("id"),
                            "timestamp": msg.get("created_time"),
                        }
                    )
                    if len(messages) >= max_results:
                        break

            logger.info(f"Instagram: fetched {len(messages)} unread message(s).")
            return messages

        except Exception as exc:
            logger.error(f"Instagram: failed to fetch messages — {exc}")
            return []

    def send_message(self, recipient_id: str, text: str) -> bool:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{BASE_URL}/me/messages",
                    params={"access_token": self.page_access_token},
                    json={
                        "recipient": {"id": recipient_id},
                        "message": {"text": text},
                    },
                )
                resp.raise_for_status()
            logger.info(f"Instagram: reply sent to {recipient_id}.")
            return True
        except Exception as exc:
            logger.error(f"Instagram: failed to send message to {recipient_id} — {exc}")
            return False
