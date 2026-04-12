import os
from dotenv import load_dotenv

# Load from .env file
load_dotenv()

# Application Settings
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_TITLE = os.getenv("APP_TITLE", "AI-Powered BizClone")
HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8000))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Timezone Configuration
# Used by: appointment scheduling, birthday email scheduler, ICS calendar invitations
# All time-based services should use this timezone for consistency
TIMEZONE = os.getenv("TIMEZONE", "Europe/Berlin")

# Intent Labels (must match IntentType enum in channels/schemas.py)
PRICE_INQUERY = "pricing_inquiry"
APPOINTMENT = "appointment_booking_request"
CANCELLATION = "cancellation_request"
WORKING_HOUR = "business_hours_question"
EMERGENCY = "emergency_service_request"
FAQ = "general_faq_question"

# Vector DB
PERSIST_DIR = "data/chroma_email_db"
COLLECTION_NAME = "bizclone_email_kb"
TRANSFORMER = "all-MiniLM-L6-v2"

# Knowledge Base
UPDATES_LOG_PATH = "data/kb/updates/feedback_log.jsonl"
KB_UPDATES = "data/kb/updates"
KB_VERSIONS_DIR = "data/kb/versions"

INITIAL_KB_JSON_PATH = "database/initial_email_kb.json"

# Business Configuration (loaded from .env)
BUSINESS_DOMAIN = os.getenv("BUSINESS_DOMAIN", "plumbing")
COMPANY_SIGNATURE = os.getenv("COMPANY_SIGNATURE", "").replace("\\n", "\n")
COMPANY_EMAIL = os.getenv("COMPANY_EMAIL", "support@bizclone.com")

# Gmail API (loaded from .env)
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_PATH", "config/google/credentials.json")
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_PATH", "config/google/token.json")

# Backward compatibility aliases for Gmail client
GMAIL_CREDENTIALS_FILE = GOOGLE_CREDENTIALS_FILE
GMAIL_TOKEN_FILE = GOOGLE_TOKEN_FILE

# Scheduler
BOOKING_SLOTS_FILE = "data/scheduling/booking_slots.json"
BOOKINGS_FILE = os.getenv("BOOKINGS_FILE", "bookings.jsonl")
BOOKINGS_DIR = os.getenv("BOOKINGS_DIR", "data/scheduling")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")
REQUIRED_TABLES = ['email_history', 'booking', 'knowledge_base', 'kb_feedback', 'customer', 'calendar_account']

# Urgency Detection Configuration
# Defines how emails are escalated based on urgency level (not intent)
ESCALATION_CONFIG = {
    "CRITICAL": {
        "auto_reply": False,           # Always escalate, never auto-reply
        "owner_notification": True,    # Send owner notification immediately
        "sla_hours": 1                 # SLA: owner should respond within 1 hour
    },
    "HIGH": {
        "auto_reply": False,           # Always escalate
        "owner_notification": True,
        "sla_hours": 24                # SLA: owner should respond within 24 hours
    },
    "NORMAL": {
        "auto_reply": True,            # Safe to auto-reply
        "owner_notification": False,
        "sla_hours": 48                # SLA: async processing acceptable
    }
}

# Legacy API Keys (from .env)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ALLOWED_SENDERS = os.getenv("ALLOWED_SENDERS", "").split(",") if os.getenv("ALLOWED_SENDERS") else []
