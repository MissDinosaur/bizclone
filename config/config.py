# Intent Labels
PRICE_INQUERY = "pricing inquiry",
APPOINTMENT = "appointment booking request",
CANCELLATION = "cancellation request",
WORKING_HOUR = "business hours question",
EMERGENCY = "emergency service request",
FAQ = "general FAQ question"

# Vector DB
PERSIST_DIR = "data/chroma_email_db"
COLLECTION_NAME = "bizclone_email_kb"
TRANSFORMER = "all-MiniLM-L6-v2"

# Knowledge Base
UPDATES_LOG_PATH = "data/kb/updates/feedback_log.jsonl"
KB_UPDATES = "data/kb/updates"
KB_VERSIONS_DIR = "data/kb/versions"
LATEST_KB_JSON_FILE_PATH = "data/kb/latest_email_kb.json"

# Business
BUSINESS_DOMAIN = "plumbing"
COMPANY_SIGNATURE = """
Jacqueline LI
Operations Manager
Hamburg Plumbing Solutions
+49 40 12345678
info@hamburgplumbing.de
"""

# Gmail API
GMAIL_CREDENTIALS_FILE = "config/gmail/credentials.json"
GMAIL_TOKEN_FILE = "config/gmail/token.json"