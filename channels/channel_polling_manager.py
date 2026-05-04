"""
Channel Polling Manager

Orchestrates polling for multiple input channels (Email, Teams, WhatsApp, Call, Facebook.)
"""
import logging
from channels.email.email_watcher import EmailWatcher
from channels.call.call_watcher import CallWatcher
from channels.teams.teams_watcher import TeamsWatcher
from channels.whatsapp.whatsapp_watcher import WhatsAppWatcher
from channels.facebook.facebook_watcher import FacebookWatcher
from channels.instagram.instagram_watcher import InstagramWatcher

logger = logging.getLogger(__name__)


class ChannelPollingManager:
    """
    Manages all channel watchers and their lifecycle.
    Usage:
        manager = ChannelPollingManager()
        manager.start_all()  # At app startup
        manager.stop_all()   # At app shutdown
    """

    def __init__(self, config: dict = None):
        """
        Initialize the polling manager.
        Args:
            config: Optional configuration dict with channel settings. Sample format:
                {
                    "email": {"enabled": True, "poll_interval": 300},
                    "call": {"enabled": False, "poll_interval": 300},
                    "teams": {"enabled": False, "poll_interval": 300},
                    "whatsapp": {"enabled": False, "poll_interval": 300},
                    "facebook": {"enabled": False, "poll_interval": 300},
                }
        """
        self.config = config or {}
        self.watchers = {}
        self._initialize_watchers()

    def _initialize_watchers(self):
        """Initialize all configured channel watchers."""
        # Email watcher (enabled by default)
        email_config = self.config.get("email", {"enabled": True, "poll_interval": 300})
        if email_config.get("enabled", True):
            self.watchers["email"] = EmailWatcher(
                poll_interval=email_config.get("poll_interval", 300)
            )

        # Call watcher
        call_config = self.config.get("call", {"enabled": False, "poll_interval": 300})
        if call_config.get("enabled", False):
            self.watchers["call"] = CallWatcher(
                poll_interval=call_config.get("poll_interval", 300)
            )

        # Teams watcher
        teams_config = self.config.get("teams", {"enabled": False, "poll_interval": 300})
        if teams_config.get("enabled", False):
            self.watchers["teams"] = TeamsWatcher(
                poll_interval=teams_config.get("poll_interval", 300)
            )

        # WhatsApp watcher
        whatsapp_config = self.config.get("whatsapp", {"enabled": False, "poll_interval": 300})
        if whatsapp_config.get("enabled", False):
            self.watchers["whatsapp"] = WhatsAppWatcher(
                poll_interval=whatsapp_config.get("poll_interval", 300)
            )

        # Instagram watcher
        instagram_config = self.config.get("instagram", {"enabled": False, "poll_interval": 60})
        if instagram_config.get("enabled", False):
            self.watchers["instagram"] = InstagramWatcher(
                poll_interval=instagram_config.get("poll_interval", 60)
            )

        # Facebook watcher
        facebook_config = self.config.get("facebook", {"enabled": False, "poll_interval": 300})
        if facebook_config.get("enabled", False):
            self.watchers["facebook"] = FacebookWatcher(
                poll_interval=facebook_config.get("poll_interval", 300)
            )

    def start_all(self):
        """
        Start all configured channel watchers.
        Called during FastAPI startup event.
        """
        if not self.watchers:
            logger.warning("No channel watchers configured")
            return

        logger.info(f"Starting {len(self.watchers)} channel watcher(s)...")
        for channel_name, watcher in self.watchers.items():
            watcher.start()
        logger.info("All channel watchers started")

    def stop_all(self):
        """
        Stop all channel watchers gracefully.
        Called during FastAPI shutdown event.
        """
        logger.info("Stopping all channel watchers...")
        for channel_name, watcher in self.watchers.items():
            watcher.stop()
        logger.info("All channel watchers stopped")

    def get_watcher(self, channel_name: str):
        """
        Get a specific watcher by channel name.
        Args:
            channel_name: Name of the channel (e.g., "email", "teams") 
        Returns:
            BaseChannelWatcher or None if not found
        """
        return self.watchers.get(channel_name)

    def list_active_channels(self):
        """Return list of active channel names."""
        return list(self.watchers.keys())
