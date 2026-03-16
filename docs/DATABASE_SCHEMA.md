# Database Schema Documentation

## Overview

BizClone uses a comprehensive PostgreSQL schema with 4 tables, optimized for:
- Email conversation history with full context
- KB version control with rollback capability
- Appointment bookings across multiple channels
- Audit trail for KB changes

## Database Initialization

### Automatic (Recommended)

Tables are automatically created when the application starts via SQLAlchemy ORM:

```python
# In main.py startup event
Base.metadata.create_all(engine)
```

Or through Docker initialization script:
```sql
-- data/init-db.sql runs automatically on container startup
-- Creates all schema with proper sequences and indexes
```

### Manual SQL Creation

If you need to create tables manually, use the SQL below:

```sql
-- Create sequences for auto-increment
CREATE SEQUENCE IF NOT EXISTS knowledge_base_version_number_seq START 1;
CREATE SEQUENCE IF NOT EXISTS kb_feedback_id_seq START 1;

-- EmailHistory Table
CREATE TABLE IF NOT EXISTS email_history (
    id SERIAL PRIMARY KEY,
    customer_email VARCHAR(255) NOT NULL,
    sender_category VARCHAR(50),
    subject VARCHAR(500),
    body TEXT NOT NULL,
    our_reply TEXT,
    intent VARCHAR(100),
    channel VARCHAR(50) DEFAULT 'email',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_email ON email_history(customer_email);
CREATE INDEX idx_timestamp ON email_history(timestamp);
CREATE INDEX idx_intent ON email_history(intent);
CREATE INDEX idx_customer_timestamp ON email_history(customer_email, timestamp);

-- Booking Table
CREATE TABLE IF NOT EXISTS booking (
    id VARCHAR(50) PRIMARY KEY,
    customer_email VARCHAR(255) NOT NULL,
    slot TIMESTAMP NOT NULL,
    channel VARCHAR(50),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'confirmed',
    booked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reminder_sent BOOLEAN DEFAULT FALSE,
    cancellation_reason TEXT,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_customer_email_booking ON booking(customer_email);
CREATE INDEX idx_slot ON booking(slot);
CREATE INDEX idx_status ON booking(status);
CREATE INDEX idx_customer_slot ON booking(customer_email, slot);
CREATE INDEX idx_status_booked ON booking(status, booked_at);

-- KnowledgeBase Table (Consolidated from kb_version + kb_current)
CREATE TABLE IF NOT EXISTS knowledge_base (
    version_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    kb_data JSONB NOT NULL,
    services JSONB,
    policies JSONB,
    faqs JSONB,
    change_description TEXT,
    updated_by VARCHAR(255),
    is_active BOOLEAN DEFAULT FALSE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timestamp ON knowledge_base(timestamp);
CREATE INDEX idx_is_active ON knowledge_base(is_active);
CREATE INDEX idx_last_updated ON knowledge_base(last_updated);

-- KBFeedback Table (Audit trail)
CREATE TABLE IF NOT EXISTS kb_feedback (
    id SERIAL PRIMARY KEY,
    operation VARCHAR(50),
    kb_field VARCHAR(100),
    customer_question TEXT,
    owner_correction TEXT,
    service_name VARCHAR(255),
    service_description TEXT,
    service_price VARCHAR(100),
    kb_version_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kb_version_id) REFERENCES knowledge_base(version_id) ON DELETE SET NULL
);

CREATE INDEX idx_kb_field ON kb_feedback(kb_field);
CREATE INDEX idx_created_at ON kb_feedback(created_at);
CREATE INDEX idx_created_at_operation ON kb_feedback(created_at, operation);
```

## Table Descriptions

### 1. **email_history**
Stores all incoming and outgoing emails for context-aware LLM replies.

| Column | Type | Purpose |
|--------|------|---------|
| id | SERIAL | Auto-increment primary key |
| customer_email | VARCHAR(255) | Customer's email address (indexed for fast lookup) |
| sender_category | VARCHAR(50) | "customer" or "our_reply" |
| subject | VARCHAR(500) | Email subject line |
| body | TEXT | Email body content |
| our_reply | TEXT | Our response to the customer |
| intent | VARCHAR(100) | Classified intent (booking, inquiry, complaint, etc.) |
| channel | VARCHAR(50) | Channel source (email, teams, whatsapp, etc.) |
| timestamp | TIMESTAMP | When email was received or sent |

**Indexes:**
- `idx_customer_email`: Fast lookup by customer
- `idx_customer_timestamp`: Most common query (customer + time range)
- `idx_timestamp`: Range queries for recent emails
- `idx_intent`: Filter by conversation intent

### 2. **booking**
Stores all appointment bookings across channels with status tracking.

| Column | Type | Purpose |
|--------|------|---------|
| id | VARCHAR(50) | Unique booking ID (BKyyyymmdd-hhmmss) |
| customer_email | VARCHAR(255) | Customer's email |
| slot | TIMESTAMP | Appointment date/time |
| channel | VARCHAR(50) | Booking channel (email, teams, whatsapp) |
| notes | TEXT | Additional booking notes |
| status | VARCHAR(50) | confirmed/cancelled/completed/no-show |
| booked_at | TIMESTAMP | When booking was created |
| reminder_sent | BOOLEAN | Whether reminder was sent |
| cancellation_reason | TEXT | Reason for cancellation |
| cancelled_at | TIMESTAMP | When booking was cancelled |

**Indexes:**
- `idx_customer_slot`: Check for duplicate bookings
- `idx_status_booked`: Find upcoming appointments
- `idx_slot`: Availability checking

### 3. **knowledge_base** *(Consolidated from kb_version + kb_current)*
Maintains complete KB with version history, rollback capability, and caching.

| Column | Type | Purpose |
|--------|------|---------|
| version_id | SERIAL | Unique auto-incremented version identifier (PRIMARY KEY) |
| timestamp | TIMESTAMP | When version was created |
| kb_data | JSONB | Complete KB snapshot (services, policies, FAQs) |
| services | JSONB | Cached services section for fast access |
| policies | JSONB | Cached policies section for fast access |
| faqs | JSONB | Cached FAQs section for fast access |
| change_description | TEXT | What changed in this version |
| updated_by | VARCHAR(255) | Who made the change (system/user) |
| is_active | BOOLEAN | Whether this is the current active version |
| last_updated | TIMESTAMP | When this version was last modified |
| created_at | TIMESTAMP | When record was created |

**Key Features:**
- **Single table design**: Eliminates redundancy between separate kb_version and kb_current tables
- **Auto-incrementing version_id**: Simplifies version tracking and rollback
- **Cached columns**: services/policies/faqs fields avoid JSON parsing on each retrieval
- **is_active flag**: Direct indicator of active KB (no joins needed)

**Indexes:**
- `idx_is_active`: Quick lookup of current KB (WHERE is_active=TRUE)
- `idx_timestamp`: Historical version queries
- `idx_last_updated`: Track most recently updated versions

**Query Active KB:**
```sql
-- Option 1: Direct flag lookup
SELECT * FROM knowledge_base WHERE is_active = TRUE;

-- Option 2: Latest version
SELECT * FROM knowledge_base ORDER BY version_id DESC LIMIT 1;
```

### 4. **kb_feedback**
Complete audit trail of KB modifications.

| Column | Type | Purpose |
|--------|------|---------|
| id | SERIAL | Auto-increment ID |
| operation | VARCHAR(50) | "insert" or "update" |
| kb_field | VARCHAR(100) | "service", "policy", or "faq" |
| customer_question | TEXT | Original customer question |
| owner_correction | TEXT | Owner's correction/clarification |
| service_name | VARCHAR(255) | Service being modified (if applicable) |
| service_description | TEXT | Service description |
| service_price | VARCHAR(100) | Service price |
| kb_version_id | INTEGER | Link to knowledge_base.version_id (FK) |
| created_at | TIMESTAMP | When feedback was recorded |

**Indexes:**
- `idx_kb_field`: Filter changes by KB field
- `idx_created_at_operation`: Most recent changes
- FK to knowledge_base: Maintains referential integrity

## Key Design Features

### 1. **Consolidated KB Storage**
**Before:** 2 separate tables (kb_version for history, kb_current for caching)
```
KBFeedback → KBVersion ← KBCurrent (1:1)
```

**After:** 1 unified table (knowledge_base)
```
KBFeedback → KnowledgeBase
```

**Benefits:**
- Simpler schema (1 table instead of 2)
- Faster queries (no JOIN needed to get active KB)
- Single source of truth
- Clearer intent with is_active flag

### 2. **Foreign Key Relationships**
```
KBFeedback.kb_version_id → KnowledgeBase.version_id (ON DELETE SET NULL)
```
Ensures data consistency and maintains audit trail even if versions are deleted.

### 3. **JSONB Columns**
- `knowledge_base.kb_data`: Stores complete KB state as JSON
- `knowledge_base.services/policies/faqs`: Cached subsets for performance
- Allows flexible schema changes without migrations

### 4. **Auto-increment Version Numbers**
```sql
-- Version ID sequence
CREATE SEQUENCE IF NOT EXISTS knowledge_base_version_number_seq START 1;
```
Ensures versions are numbered sequentially for easy rollback logic.

## Query Examples

### Get Customer Conversation History (Last 10 Emails)
```sql
SELECT * FROM email_history
WHERE customer_email = 'client@example.com'
ORDER BY timestamp DESC
LIMIT 10;
```

### Find Available Slots
```sql
-- Query booked slots:
SELECT slot FROM booking
WHERE status = 'confirmed'
AND slot >= CURRENT_DATE
ORDER BY slot;
```

### Get Active KB (Single Table, No Joins)
```sql
-- Fast lookup
SELECT * FROM knowledge_base WHERE is_active = TRUE;

-- Or get latest version
SELECT * FROM knowledge_base ORDER BY version_id DESC LIMIT 1;
```

### KB Version History
```sql
SELECT version_id, timestamp, change_description, updated_by
FROM knowledge_base
ORDER BY version_id DESC
LIMIT 20;
```

### Rollback KB to Previous Version
```sql
-- Restore version 5 (Simplified - single table update)
BEGIN;
UPDATE knowledge_base SET is_active = FALSE;
UPDATE knowledge_base SET is_active = TRUE WHERE version_id = 5;
COMMIT;
```

### Recent KB Changes (Audit Trail)
```sql
SELECT created_at, operation, kb_field, customer_question, owner_correction
FROM kb_feedback
WHERE created_at > CURRENT_DATE - INTERVAL '7 days'
ORDER BY created_at DESC;
```


### Monitor Database Size
```sql
-- Check table sizes
SELECT 
  table_name,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
JOIN information_schema.tables ON table_name = tablename
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

