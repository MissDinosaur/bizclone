from fastapi import FastAPI
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Suppress verbose logs from transformer/huggingface libraries
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("transformers.utils.hub").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

# Initialize logging first
import config.logger_config as logger_config
logger = logger_config.get_logger(__name__)

# Database initialization
from database.initialization import init_database

# Email agent core
from channels.channel_polling_manager import ChannelPollingManager
from api.kb_learning_api import router as learning_router
from ui.kb_feedback_ui import router as feedback_ui_router
from ui.review_email_ui import router as review_router
from config.config import APP_TITLE, HOST, PORT

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
    "instagram": {
        "enabled": os.getenv("CHANNEL_INSTAGRAM_ENABLED", "False").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_INSTAGRAM_POLL_INTERVAL", 60))
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
    - Initialize database tables and load initial KB data
    - Pre-initialize EmailAgent to trigger KB loading to vector store
    - Start all configured channel polling services in background threads
    """
    logger.info("Application startup initiated...")
    
    # Initialize database (creates tables, loads KB data)
    init_database()
    
    # Pre-initialize EmailAgent to trigger KB loading to vector store
    # (This ensures KB is loaded at startup, not on first email)
    from channels.email.email_agent import get_email_agent
    try:
        get_email_agent()
        logger.info("✓ EmailAgent initialized, KB loaded to vector store")
    except Exception as e:
        logger.warning(f"Failed to pre-initialize EmailAgent: {e}")
    
    # Start channel polling
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
# Health Check Endpoint
# =============================
@app.get("/health")
def health_check():
    """Simple health check endpoint for Docker healthcheck"""
    return {"status": "healthy", "message": "BizClone is running"}


# =============================
# Include routers
# =============================
app.include_router(learning_router)       # Core Learning API, updating KB
app.include_router(feedback_ui_router)    # Owner Correct the KB via UI
app.include_router(review_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False  # Disable HTTP access logs (health checks, etc.)
    )
