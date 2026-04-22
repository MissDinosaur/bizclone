# Channel Integration Guide

This document explains how to integrate a new input channel (Teams, WhatsApp, Telegram, etc.) into the BizClone multi-channel agent system.

## Architecture Overview

The channel system follows a **template method pattern** with three main components:

```
┌─────────────────────────────────────────┐
│   Channel Polling Manager (main.py)    │
│   - Orchestrates all active channels   │
│   - Lifecycle management (start/stop)  │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┴──────────┬──────────────┬──────────────┐
        ▼                     ▼              ▼              ▼
   EmailWatcher          TeamsWatcher  WhatsAppWatcher  CallWatcher
   (email channel)       (teams)       (whatsapp)       (call)
        │                     │             │              │
        └─────────────────────┴─────────────┴──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │  BaseChannelWatcher (ABC)  │
                │  - Polling loop logic      │
                │  - Thread management       │
                │  - Error handling          │
                └────────────────────────────┘
```

## Component Structure

### 1. BaseChannelWatcher (Abstract Base Class)

Located in `channels/base_watcher.py`, provides:

- **`_run_loop()`** - Main polling loop that continuously:
  - Calls `fetch_unread_messages()` 
  - Processes each message via `process_message()`
  - Sleeps for `poll_interval` seconds
  - Handles errors gracefully

- **`start()`** - Spawns daemon thread to run the watcher

- **`stop()`** - Gracefully shuts down the watcher

- **Abstract Methods** (must be implemented by subclasses):
  - `fetch_unread_messages()` - Retrieve new messages from the channel
  - `process_message(message)` - Process a single message through the agent pipeline

### 2. Channel Agent

Each channel has an Agent class that:
- Processes incoming messages through NLP pipeline
- Handles scheduling/booking requests
- Returns standardized response schema

Example: `EmailAgent` in `channels/email/email_agent.py`

### 3. Channel Watcher

Each channel has a Watcher class that:
- Inherits from `BaseChannelWatcher`
- Implements `fetch_unread_messages()` - API-specific retrieval
- Implements `process_message()` - Routes to Agent, handles responses

Example: `EmailWatcher` in `channels/email/email_watcher.py`

---

## Step-by-Step Integration Guide

### Step 1: Create Channel Directory Structure

Create folder: `channels/{channel_name}/`

```
channels/
├── email/
│   ├── __init__.py
│   ├── email_agent.py
│   ├── email_watcher.py
│   ├── gmail_client.py
│   ├── parser.py
│   └── intent_classifier.py
│
├── whatsapp/                 
│   ├── __init__.py
│   ├── whatsapp_agent.py     # Process messages
│   ├── whatsapp_watcher.py   # Polling logic
│   ├── whatsapp_client.py    # API wrapper (Twilio/Meta)
│   └── parser.py             # Message parsing (if needed)
```

### Step 2: Create Channel Client (API Wrapper)

**File:** `channels/{channel_name}/{channel_name}_client.py`

Example for WhatsApp (using Twilio):

```python
# channels/whatsapp/whatsapp_client.py
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)


class WhatsAppClient:
    """Wrapper for WhatsApp API operations (Twilio)."""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number  # WhatsApp number format: whatsapp:+1234567890
        ...
    
    def fetch_unread_messages(self, max_results=10):
        ...

```

### Step 3: Create Channel Agent

**File:** `channels/{channel_name}/{channel_name}_agent.py`

The agent processes messages and must **always return `ChannelMessageResponseSchema`**.

Example for WhatsApp:

```python
# channels/whatsapp/whatsapp_agent.py
import logging
from channels.schemas import (
    ChannelMessageResponseSchema,
    IntentType,
    MessageStatus,
    BookingResponseSchema
)
from channels.email.intent_classifier import IntentClassifier
from rag.rag_pipeline import EmailRAGPipeline
from scheduling.scheduler import check_availability, book_slot
import config.config as cfg

logger = logging.getLogger(__name__)


class WhatsAppAgent:
    """Process WhatsApp messages through the agent pipeline."""
    
    def __init__(self):
        self.intent_model = IntentClassifier()
        self.rag = EmailRAGPipeline()
    
    def process_message(self, message: dict) -> ChannelMessageResponseSchema:
        ...

    
    def _handle_booking_request(self, user_phone: str, message_text: str) -> dict:
        """Handle appointment booking for WhatsApp."""
        ...

    
    def _intent_to_enum(self, intent_str: str) -> IntentType:
        """Convert intent string to IntentType enum (15 categories)."""
        intent_mapping = {
        }
        return intent_mapping.get(intent_str, IntentType.FAQ)


_whatsapp_agent = WhatsAppAgent()


def process_message(message: dict) -> ChannelMessageResponseSchema:
    """Convenience function for backward compatibility."""
    return _whatsapp_agent.process_message(message)
```

### Step 4: Create Channel Watcher

**File:** `channels/{channel_name}/{channel_name}_watcher.py`

The watcher fetches messages and processes them.

Example for WhatsApp:

```python
# channels/whatsapp/whatsapp_watcher.py
import logging
import os
from channels.base_watcher import BaseChannelWatcher
from channels.whatsapp.whatsapp_client import WhatsAppClient
from channels.whatsapp.whatsapp_agent import process_message
from channels.schemas import MessageStatus

logger = logging.getLogger(__name__)


class WhatsAppWatcher(BaseChannelWatcher):
    """Background WhatsApp polling service (via Twilio)."""
    
    def __init__(self, poll_interval=300):
        super().__init__(channel_name="whatsapp", poll_interval=poll_interval)
        ...
    
    def fetch_unread_messages(self):
        """Fetch unread messages from WhatsApp."""
        ...
    
    def process_message(self, message: dict):
        ...
```

### Step 5: Update Channel Polling Manager

**File:** `channels/channel_polling_manager.py`

Add your new channel to the manager:

```python
from channels.whatsapp.whatsapp_watcher import WhatsAppWatcher  # ← Add import

class ChannelPollingManager:
    def _initialize_watchers(self):
        # ... existing code ...
        
        # Add your new channel if it does not exist here
        whatsapp_config = self.config.get("whatsapp", {"enabled": False, "poll_interval": 300})
        if whatsapp_config.get("enabled", False):
            self.watchers["whatsapp"] = WhatsAppWatcher(
                poll_interval=whatsapp_config.get("poll_interval", 300)
            )
```

### Step 6: Update Environment Configuration

**File:** `.env`

Add configuration for your channel:

```dotenv
# WhatsApp Configuration (Twilio)
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
WHATSAPP_FROM_NUMBER=whatsapp:+1234567890
CHANNEL_WHATSAPP_ENABLED=True
CHANNEL_WHATSAPP_POLL_INTERVAL=300

# PostgreSQL Database (Required for all channels)
DATABASE_URL=postgresql://user:password@host:5432/database_name
```

**File:** `.env.example`

Add template:

```dotenv
# WhatsApp Configuration (Twilio)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token
WHATSAPP_FROM_NUMBER=whatsapp:+1234567890
CHANNEL_WHATSAPP_ENABLED=False
CHANNEL_WHATSAPP_POLL_INTERVAL=300

# PostgreSQL Database (Required)
DATABASE_URL=postgresql://user:password@host:5432/database_name
```

### Step 7: Update main.py Configuration

**File:** `main.py`

Add to CHANNEL_CONFIG:

```python
CHANNEL_CONFIG = {
    "email": { ... },
    # ... other channels ...
    "whatsapp": {
        "enabled": os.getenv("CHANNEL_WHATSAPP_ENABLED", "False").lower() == "true",
        "poll_interval": int(os.getenv("CHANNEL_WHATSAPP_POLL_INTERVAL", 300))
    },
}
```

---

## Data Persistence with PostgreSQL

All channels integrate with PostgreSQL database for persistent storage of:

### 1. Email History Storage

Each processed message is stored in the `email_history` table:

```python
# channels/email/email_watcher.py (example)
from channels.email.email_history_store import EmailHistoryStore

store = EmailHistoryStore()

def process_message(self, message: dict):
    # ... process message ...
    
    # Store email in database
    store.save_email(
        customer_email=message['from'],
        sender_category='customer',
        subject=message['subject'],
        body=message['body'],
        intent=result.intent.value,
        channel='email',
        timestamp=datetime.utcnow()
    )
```

### 2. Booking Storage

When a booking is confirmed, it's stored in the `booking` table:

```python
from scheduling.scheduler import create_booking

def _handle_booking_request(self, customer_email: str, slot: datetime):
    booking_id = create_booking(
        customer_email=customer_email,
        slot=slot,
        channel='whatsapp',
        notes='Booked via WhatsApp'
    )
    return booking_id
```

### 3. KB Feedback Audit Trail

When owners correct the KB, changes are tracked in `kb_feedback` table:

```python
from knowledge_base.kb_store import KBStore

kb_store = KBStore()

# Automatically linked when KB updates occur
kb_store.save_feedback(
    feedback_entry={
        'operation': 'update',
        'kb_field': 'policy',
        'customer_question': None,
        'owner_correction': 'Updated policy text',
        'policy_name': 'travel_fee'
    },
    kb_version_id=version_number
)
```

### Database Initialization

On application startup, PostgreSQL tables are automatically created if they don't exist:

```python
# database/initialization.py
from database.orm_models import Base
Base.metadata.create_all(engine)  # Creates all tables from ORM models
```

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for complete schema documentation.

---

## Response Schema Requirements

**All channels MUST return `ChannelMessageResponseSchema`:**

```python
{
    "channel": "whatsapp",                 # Channel name
    "status": "auto_send",                 # auto_send, needs_review, or failed
    "intent": "appointment_booking_request",  # From IntentType enum
    "reply": "Your appointment is booked...",  # Generated response
    "booking": {                           # Optional
        "id": "BK20260303...",
        "slot": "2026-03-05 10:00",
        "customer_email": "user@example.com",
        "channel": "whatsapp",
        "status": "confirmed",
        "booked_at": "2026-03-03T10:30:00",
        "notes": "..."
    },
    "retrieved_docs": ["Service_Info", "Pricing"],  # Optional KB docs
    "error_code": null,
    "error_message": null
}
```

---

## Common Implementation Patterns

### Pattern 1: Authentication

```python
# Store credentials securely in environment variables
def __init__(self):
    self.api_token = os.getenv("CHANNEL_API_TOKEN")
    if not self.api_token:
        raise ValueError("API token not configured")
```

### Pattern 2: Message Parsing

Different channels have different message formats. Create a parser:

```python
# channels/whatsapp/parser.py
def parse_whatsapp_message(raw_message: dict) -> dict:
    ...

```

### Pattern 3: Response Handling

```python
def process_message(self, message: dict):
    result = process_message(message)
    
    if result.status == MessageStatus.NEEDS_REVIEW:
        # Store for owner review
        save_for_review(result)
    elif result.status == MessageStatus.AUTO_SEND:
        # Send reply back through channel
        self.send_reply(message, result.reply)
    else:  # failed
        logger.error(f"whatsapp - processing failed: {result.error_message}")
```

---

## Database Requirements

All channels require PostgreSQL database for:
- Storing email conversation history (`email_history` table)
- Persistent booking records (`booking` table)
- KB version control and audit trail (`knowledge_base`, `kb_feedback` tables)

### Database Setup

**1. Docker Deployment (Recommended):**
```bash
docker-compose up --build -d
```
PostgreSQL automatically initializes with schema and initial data.

**2. Local Development:**
```bash
# Start PostgreSQL
pg_ctl start

# Create database
createdb bizclone_db -U your_user

# Set environment variable
export DATABASE_URL="postgresql://your_user:password@localhost:5432/bizclone_db"

# Start application (tables auto-create on startup)
python main.py
```

**3. Verify Database Connection:**
```bash
# Test connection
psql postgresql://user:password@host:5432/database_name -c "SELECT 1"

# Inside application logs
[INFO] [database.initialization] ✓ PostgreSQL connected: PostgreSQL 16.13
[INFO] [database.initialization] ✓ All 4 required tables exist
```

For detailed schema documentation, see [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md).

---

## Testing Your Channel Integration

### Unit Tests
Example:

Create `tests/test_whatsapp_agent.py`:
```python
import pytest
from channels.whatsapp.whatsapp_agent import WhatsAppAgent
from channels.schemas import ChannelMessageResponseSchema

@pytest.fixture
def agent():
    return WhatsAppAgent()

def test_whatsapp_agent_processes_appointment(agent):
    ...

```

### Integration Tests
Example:

Create `tests/test_whatsapp_watcher.py`:
```python
import pytest
from channels.whatsapp.whatsapp_watcher import WhatsAppWatcher

@pytest.fixture
def watcher():
    # Requires Twilio config in environment
    return WhatsAppWatcher(poll_interval=10)

def test_whatsapp_watcher_initialization(watcher):
    assert watcher.channel_name == "whatsapp"
    assert watcher.running is False

```
---

## Checklist for Adding a New Channel

- Create channel directory: `channels/{channel_name}/`
- Implement `{channel_name}_client.py` - API wrapper
  - `fetch_unread_messages()` method
  - `send_message()` or equivalent method
  - Error handling for API failures
- Implement `{channel_name}_agent.py` - Message processing
  - `process_message()` returns `ChannelMessageResponseSchema`
  - Intent to enum conversion via `_intent_to_enum()`
  - Booking request handling (if needed)
  - Emergency detection and handling
- Implement `{channel_name}_watcher.py` - Polling service
  - Inherits from `BaseChannelWatcher`
  - Implements `fetch_unread_messages()`
  - Implements `process_message()`
  - Routes to agent and sends replies
- Update `channels/channel_polling_manager.py` - Add to manager if there no your channel manager
- Update `.env` and `.env.example` - Add all required credentials and config
- Update `main.py` CHANNEL_CONFIG - Register channel with enable flag and poll interval
- Create unit tests in `tests/test_{channel_name}_agent.py`
- Create integration tests in `tests/test_{channel_name}_watcher.py`
- Update README.md with channel-specific setup instructions
- Test end-to-end: start app, verify logs, send test message

---

## Support

For questions about integrating channels:
1. Check existing implementations (`email/`, etc.)
2. Review `channels/schemas.py` for required response format
3. Check `channels/base_watcher.py` for the polling loop contract
4. Look at test examples in `tests/` directory
