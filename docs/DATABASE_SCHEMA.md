# Database Schema

## Overview

PostgreSQL database with 6 tables supporting email conversations, appointment bookings, KB versioning with audit trail, customer profiles, and calendar integrations.

**Tables:** EmailHistory | Booking | KnowledgeBase | KBFeedback | Customer | CalendarAccount

## Table Schemas

### 1. email_history
Customer email conversations with LLM context and Gmail threading.

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| id | INTEGER | PK | Auto-increment |
| customer_email | VARCHAR(255) | | Customer email address |
| sender_category | VARCHAR(50) | | 'customer', 'support', 'birthday' |
| subject | VARCHAR(500) | | Email subject |
| body | TEXT | | Email body content |
| thread_id | VARCHAR(255) | | Gmail thread ID (conversation grouping) |
| message_id | VARCHAR(255) | | Gmail message ID (individual email ref) |
| intent | VARCHAR(100) | | Classified intent (appointment, complaint, etc.) |
| channel | VARCHAR(50) | | Source channel (email, teams, whatsapp) |
| timestamp | DATETIME | | Email timestamp |
| created_at | DATETIME | | Record creation time |

**Indexes:**
- `idx_customer_timestamp` (customer_email, timestamp)
- `idx_intent` (intent)

**Purpose:** Full conversation history for LLM context in email generation

---

### 2. booking
Appointment reservations across all channels.

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| id | VARCHAR(50) | PK | BKyyyymmdd-hhmmss format |
| customer_email | VARCHAR(255) | | Customer booking |
| slot | DATETIME | | Appointment date/time |
| channel | VARCHAR(50) | | Booking source (email, teams, etc.) |
| notes | TEXT | | Service type, customer notes |
| status | VARCHAR(50) | | confirmed/cancelled/completed/no-show |
| booked_at | DATETIME | | Booking creation time |
| reminder_sent | BOOLEAN | | Whether reminder email was sent |
| cancellation_reason | TEXT | | Reason if cancelled |
| cancelled_at | DATETIME | | Cancellation time |
| created_at | DATETIME | | Record creation |

**Indexes:**
- `idx_customer_slot` (customer_email, slot)
- `idx_status_date` (status, booked_at)

**Purpose:** Track all appointments with status and reminder tracking

---

### 3. knowledge_base
Versioned KB with item-level versioning for rollback.

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| version_id | INTEGER | PK | Version number (auto-increment) |
| kb_field | VARCHAR(50) | PK | 'faq', 'policy', or 'service' |
| item_key | VARCHAR(255) | PK | Unique item identifier |
| detail | JSON | | Full content (description, price, answer) |
| change_description | TEXT | | What changed in this version |
| updated_by | VARCHAR(255) | | Who made the update |
| is_active | BOOLEAN | | Only active=True used for RAG retrieval |
| timestamp | DATETIME | | Version creation |
| last_updated | DATETIME | | Last modification |
| created_at | DATETIME | | Record creation |

**Composite PK:** (version_id, kb_field, item_key)

**Indexes:**
- `idx_kb_field_active` (kb_field, is_active)
- `idx_kb_item_active` (kb_field, item_key, is_active)
- `idx_timestamp`, `idx_is_active`, `idx_last_updated`

**Purpose:** Versioned KB with rollback capability, RAG uses is_active=True records

---

### 4. kb_feedback
Audit trail of KB modifications (learning system).

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| id | INTEGER | PK | Auto-increment |
| operation | VARCHAR(50) | | 'add', 'update', 'delete' |
| kb_field | VARCHAR(100) | | KB field type |
| item_key | VARCHAR(255) | | KB item identifier |
| kb_version_id | INTEGER | | FK ref to knowledge_base.version_id |
| customer_question | TEXT | | Original customer question |
| owner_correction | TEXT | | Owner's correction/feedback |
| service_name | VARCHAR(255) | | Service (if applicable) |
| service_description | TEXT | | Service details |
| service_price | VARCHAR(100) | | Service price |
| policy_name | VARCHAR(255) | | Policy name (if applicable) |
| created_at | DATETIME | | Feedback timestamp |

**Foreign Key:**
- Composite: (kb_version_id, kb_field, item_key) → knowledge_base

**Indexes:**
- `idx_kb_field`, `idx_created_at`, `idx_created_at_operation`
- `idx_kb_feedback_version_key` (kb_version_id, kb_field, item_key)

**Purpose:** Track KB changes for learning and audit trail

---

### 5. customer
Customer profiles for personalized service and birthday reminders.

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| customer_id | INTEGER | PK | Auto-increment |
| first_name | VARCHAR(100) | | Customer first name |
| last_name | VARCHAR(100) | | Customer last name |
| email | VARCHAR(255) | | Email (unique) |
| phone | VARCHAR(20) | | Phone number |
| date_of_birth | DATE | | For birthday email scheduler |
| home_address | TEXT | | Street address |
| city | VARCHAR(100) | | City |
| state_province | VARCHAR(100) | | State/Province |
| postal_code | VARCHAR(20) | | ZIP/Postal code |
| country | VARCHAR(100) | | Country |
| preferred_contact_method | VARCHAR(50) | | 'email', 'phone', 'sms' |
| notification_opt_in | BOOLEAN | | Consent for notifications |
| created_at | DATETIME | | Profile creation |
| updated_at | DATETIME | | Last profile update |
| last_contacted_at | DATETIME | | Timestamp of last contact |

**Indexes:**
- `idx_customer_email`, `idx_customer_dob`, `idx_customer_created`, `idx_customer_contact_pref`

**Purpose:** Customer data for personalization and birthday scheduler

---

### 6. calendar_account
OAuth integrations for staff calendar providers.

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| account_id | INTEGER | PK | Auto-increment |
| staff_id | VARCHAR(255) | | Staff member identifier |
| provider | VARCHAR(50) | | 'google' or 'outlook' |
| email | VARCHAR(255) | | Provider email/account |
| access_token | TEXT | | OAuth access token (encrypted) |
| refresh_token | TEXT | | OAuth refresh token |
| token_expires_at | DATETIME | | Token expiration time |
| is_active | BOOLEAN | | Enable/disable calendar sync |
| created_at | DATETIME | | Integration created |
| updated_at | DATETIME | | Last update |
| last_synced_at | DATETIME | | Last calendar sync |

**Indexes:**
- `idx_calendar_account_provider_email` (provider, email)
- `idx_calendar_account_staff` (staff_id, provider)
- `idx_calendar_account_active` (is_active)

**Purpose:** Multi-account calendar integrations for booking sync

---

## Initialization

**Docker (Recommended):**
```bash
docker-compose up --build -d
# Automatically creates tables and loads initial KB
```

**Local Development:**
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/bizclone_db"
python main.py  # Creates tables on startup
```

## Key Constraints

1. **EmailHistory.thread_id/message_id** - Gmail conversation threading
2. **Booking.status** - Tracks appointment lifecycle (confirmed → completed)
3. **KnowledgeBase.is_active** - Only active records used for RAG retrieval
4. **KBFeedback.FK** - Composite FK to knowledge_base for audit trail
5. **Customer.email** - Unique, used for birthday reminders
6. **CalendarAccount.is_active** - Controls booking sync to calendar

## Performance Optimization

- **RAG Queries:** Use `WHERE is_active=TRUE` on knowledge_base
- **Recent Emails:** Index on `(customer_email, timestamp)`
- **Booking Lookups:** Index on `(customer_email, slot)` and `(status, booked_at)`
- **Birthday Scheduler:** Uses `Customer.date_of_birth` index for daily query
