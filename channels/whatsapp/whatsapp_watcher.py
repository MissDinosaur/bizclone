"""
WhatsApp Channel Watcher

Background polling for unread WhatsApp messages.
"""
from channels.base_watcher import BaseChannelWatcher


class WhatsAppWatcher(BaseChannelWatcher):
    """
    Background WhatsApp Polling Service.

    Every N seconds:
    - fetch unread messages from WhatsApp
    - run WhatsApp Agent pipeline (to be implemented)
    - send automated response or hold for review
    """

    def __init__(self, poll_interval=300):
        """
        Args:
            poll_interval: Seconds between polls (default: 5 minutes)
        """
        super().__init__(channel_name="whatsapp", poll_interval=poll_interval)
        # TODO: Initialize WhatsApp client when available
        # from channels.whatsapp.whatsapp_client import WhatsAppClient
        # self.whatsapp_client = WhatsAppClient()

    def fetch_unread_messages(self):
        """
        Fetch unread messages from WhatsApp.
        
        Returns:
            List of message dictionaries
        """
        # TODO: Implement WhatsApp API integration
        # return self.whatsapp_client.fetch_unread_messages()
        return []

    def process_message(self, message):
        """
        Process a single WhatsApp message.
        
        Args:
            message: Message dictionary from WhatsApp
        """
        # TODO: Implement WhatsApp message processing
        # from channels.whatsapp.whatsapp_agent import process_whatsapp_message
        # result = process_whatsapp_message(message)
        # # Send response or hold for review
        print(f"[WHATSAPP] Processing message from {message.get('from', 'unknown')}")
