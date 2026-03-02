from fastapi import FastAPI

# Email agent core
from channels.email.email_agent import process_email
from channels.channel_polling_manager import ChannelPollingManager

from api.kb_learning_api import router as learning_router
from ui.kb_feedback_ui import router as feedback_ui_router
from ui.review_email_ui import router as review_router


app = FastAPI(title="BizClone Email Agent MVP")

# -----------------------------
# Channel Polling Configuration
# (Enable/disable channels and set poll intervals here)
# -----------------------------
CHANNEL_CONFIG = {
    "email": {
        "enabled": True,
        "poll_interval": 60  # 1 minute for testing (change to 300 for production)
    },
    "call": {
        "enabled": False,  # Set to True when Call integration is ready
        "poll_interval": 300  # 5 minutes
    },
    "teams": {
        "enabled": False,  # Set to True when Teams integration is ready
        "poll_interval": 300  # 5 minutes
    },
    "whatsapp": {
        "enabled": False,  # Set to True when WhatsApp integration is ready
        "poll_interval": 300  # 5 minutes
    },
    "facebook": {
        "enabled": False,  # Set to True when Facebook integration is ready
        "poll_interval": 300  # 5 minutes
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
    print(f"Active channels: {', '.join(active_channels)}")


@app.on_event("shutdown")
def shutdown_event():
    """
    When FastAPI shuts down:
    gracefully stop all channel watchers.
    """
    polling_manager.stop_all()

# -----------------------------
# Include routers
# -----------------------------
app.include_router(learning_router)       # Core Learning API, updating KB
app.include_router(feedback_ui_router)    # Owner Correct the KB via UI
app.include_router(review_router)
