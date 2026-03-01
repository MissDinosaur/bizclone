"""
Base Channel Watcher Class
Provides common polling logic for all input channels (Email, Teams, WhatsApp, etc.)
"""
import time
import threading
from abc import ABC, abstractmethod


class BaseChannelWatcher(ABC):
    """
    Abstract base class for all channel watchers.
    Handles common polling mechanism. Subclasses implement channel-specific logic.
    """
    def __init__(self, channel_name: str, poll_interval: int = 300):
        """
        Args:
            channel_name: Name of the channel (e.g., "email", "teams", "whatsapp")
            poll_interval: Seconds between polls (default: 5 minutes)
        """
        self.channel_name = channel_name
        self.poll_interval = poll_interval
        self.running = False
        self._thread = None

    def start(self):
        """
        Start watcher in a separate daemon thread.
        """
        if self.running:
            print(f"{self.channel_name.title()}Watcher already running.")
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"{self.channel_name.title()}Watcher started (poll interval: {self.poll_interval}s)...")

    def stop(self):
        """
        Stop the watcher thread gracefully.
        """
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print(f"{self.channel_name.title()}Watcher stopped.")

    def _run_loop(self):
        """
        Main polling loop - calls channel-specific fetch and process methods.
        """
        while self.running:
            try:
                # Fetch unread messages from channel
                messages = self.fetch_unread_messages()

                if messages:
                    print(f"[{self.channel_name.upper()}] Found {len(messages)} new message(s).")
                    for message in messages:
                        self.process_message(message)
                else:
                    print(f"[{self.channel_name.upper()}] No new messages.")

            except Exception as e:
                print(f"[{self.channel_name.upper()}] Watcher Error: {str(e)}")

            # Wait before next poll
            time.sleep(self.poll_interval)

    @abstractmethod
    def fetch_unread_messages(self):
        """
        Fetch unread messages from the channel.
        Returns:
            List of messages (channel-specific format)
        """
        pass

    @abstractmethod
    def process_message(self, message):
        """
        Process a single message from the channel.
        Args:
            message: Message object (channel-specific format)
        """
        pass
