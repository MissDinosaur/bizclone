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

# API routers
from api.kb_api import router as kb_api_router
from api.review_api import router as review_api_router
from api.calendar_data_api import router as calendar_data_api_router

# UI routers
from ui.home_ui import router as home_ui_router
from ui.static_pages_ui import router as static_pages_router

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
    - Start birthday email scheduler
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
    
    # Start birthday email scheduler
    try:
        from scheduling.birthday_scheduler import BirthdayEmailScheduler
        schedule_hour=12  # Send birthday emails at 8 AM
        schedule_minute=6
        birthday_scheduler = BirthdayEmailScheduler(
            schedule_hour=schedule_hour,  
            schedule_minute=schedule_minute
        )
        birthday_scheduler.start()
        logger.info(f"✓ Birthday email scheduler started, will send happy birthday email at {schedule_hour}:{schedule_minute}")
        app.state.birthday_scheduler = birthday_scheduler
    except Exception as e:
        logger.warning(f"Failed to start birthday email scheduler: {e}")


@app.on_event("shutdown")
def shutdown_event():
    """
    When FastAPI shuts down:
    gracefully stop all channel watchers and birthday scheduler.
    """
    polling_manager.stop_all()
    
    # Stop birthday scheduler
    if hasattr(app.state, 'birthday_scheduler'):
        app.state.birthday_scheduler.stop()
    
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
# Core API routers
app.include_router(kb_api_router)             # KB Management API - returns JSON
app.include_router(review_api_router)         # Email Review API - returns JSON
app.include_router(calendar_data_api_router)  # Calendar Data API - returns JSON

# UI routers
app.include_router(home_ui_router)            # Home page UI - main landing page
app.include_router(static_pages_router)       # Static HTML pages - KB, Review, Calendar (client-side rendering)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False  # Disable HTTP access logs (health checks, etc.)
    )
