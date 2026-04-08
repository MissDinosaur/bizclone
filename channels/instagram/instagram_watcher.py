"""
channels/instagram/instagram_watcher.py

Background polling service for Instagram DMs.
Inherits BaseChannelWatcher — implements fetch_unread_messages()
and process_message() as required by the integration contract.
"""

import logging
import os
from datetime import datetime, timezone

from channels.base_watcher import BaseChannelWatcher
from channels.instagram.instagram_client import InstagramClient
from channels.instagram.instagram_agent import process_message
from channels.instagram.parser import parse_instagram_message
from channels.schemas import MessageStatus
from knowledge_base.email_history_store import EmailHistoryStore

logger = logging.getLogger(__name__)


class InstagramWatcher(BaseChannelWatcher):
    """Background Instagram DM polling service (Meta Graph API)."""

    def __init__(self, poll_interval: int = 60):
        super().__init__(channel_name="instagram", poll_interval=poll_interval)

        self.client = InstagramClient(
            page_access_token=os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", ""),
            ig_user_id=os.getenv("INSTAGRAM_USER_ID", ""),
        )
        self.store = EmailHistoryStore()
        self._seen_message_ids: set[str] = set()

    def fetch_unread_messages(self) -> list[dict]:
        raw_messages = self.client.fetch_unread_messages(max_results=20)

        new_messages = []
        for raw in raw_messages:
            msg_id = raw.get("message_id", "")
            if msg_id and msg_id not in self._seen_message_ids:
                new_messages.append(raw)

        logger.info(f"Instagram: {len(new_messages)} new message(s) to process.")
        return new_messages

    def process_message(self, raw_message: dict) -> None:
        msg_id = raw_message.get("message_id", "")
        message = parse_instagram_message(raw_message)
        sender_id = message["from"]

        result = process_message(message)

        if result.status == MessageStatus.AUTO_SEND:
            sent = self.client.send_message(sender_id, result.reply)
            if sent:
                logger.info(f"Instagram: auto-reply sent to {sender_id}.")
            else:
                logger.error(f"Instagram: failed to send reply to {sender_id}.")

        elif result.status == MessageStatus.NEEDS_REVIEW:
            logger.warning(
                f"Instagram [{sender_id}]: message flagged for manual review — "
                f"intent={result.intent}"
            )

        else:
            logger.error(
                f"Instagram [{sender_id}]: processing failed — "
                f"{result.error_code}: {result.error_message}"
            )

        try:
            # FIX: timestamp parametresi save_email() tarafından desteklenmiyor,
            # fonksiyon kendi içinde datetime.utcnow() kullanıyor
            self.store.save_email(
                customer_email=sender_id,
                sender_category="customer",
                subject="Instagram DM",
                body=message["body"],
                intent=result.intent,
                channel="instagram",
            )
        except Exception as exc:
            logger.warning(f"Instagram: history save failed — {exc}")

        if msg_id:
            self._seen_message_ids.add(msg_id)