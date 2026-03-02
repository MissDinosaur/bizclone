from fastapi import FastAPI
import logging

# Initialize logging first
import logger_config
logger = logger_config.get_logger(__name__)

# Email agent core
from channels.channel_polling_manager import ChannelPollingManager
from api.kb_learning_api import router as learning_router
from ui.kb_feedback_ui import router as feedback_ui_router
from ui.review_email_ui import router as review_router
from config.config import APP_TITLE, HOST, PORT
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title=APP_TITLE)

# =============================
# Channel Polling Configuration
# (Enable/disable channels via .env file)
# =============================
CHANNEL_CONFIG = {
    "email": {
        "enabled": os.getenv("CHANNEL_EMAIL_ENABLED", "True").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_EMAIL_POLL_INTERVAL", 60))
    },
    "call": {
        "enabled": os.getenv("CHANNEL_CALL_ENABLED", "False").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_CALL_POLL_INTERVAL", 300))
    },
    "teams": {
        "enabled": os.getenv("CHANNEL_TEAMS_ENABLED", "False").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_TEAMS_POLL_INTERVAL", 300))
    },
    "whatsapp": {
        "enabled": os.getenv("CHANNEL_WHATSAPP_ENABLED", "False").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_WHATSAPP_POLL_INTERVAL", 300))
    },
    "facebook": {
        "enabled": os.getenv("CHANNEL_FACEBOOK_ENABLED", "False").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_FACEBOOK_POLL_INTERVAL", 300))
    },
}

polling_manager = ChannelPollingManager(config=CHANNEL_CONFIG)


@app.on_event("startup")
def startup_event():
    """
    When FastAPI launches:
    start all configured channel polling services in background threads.
    """
    polling_manager.start_all()
    active_channels = polling_manager.list_active_channels()
    logger.info(f"Application started | Active channels: {', '.join(active_channels) if active_channels else 'None'}")


@app.on_event("shutdown")
def shutdown_event():
    """
    When FastAPI shuts down:
    gracefully stop all channel watchers.
    """
    polling_manager.stop_all()
    logger.info("Application shutdown complete")

# =============================
# Include routers
# =============================
app.include_router(learning_router)       # Core Learning API, updating KB
app.include_router(feedback_ui_router)    # Owner Correct the KB via UI
app.include_router(review_router)

