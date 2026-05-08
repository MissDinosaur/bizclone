# BizClone - AI-Powered Assistant
**Note: This README.md file is of the Email Channel part.**

## Project Overview

Small enterprises—plumbers, mechanics, consultants, tutors, salon owners, and other service providers—face a critical challenge: managing customer communications and scheduling while delivering hands-on services. With limited staff and budget, these business owners often struggle to respond promptly to inquiries, manage appointments, and maintain consistent customer service quality.

**BizClone** is an AI-powered digital assistant that learns from a business owner's communication patterns, scheduling preferences, and service offerings to autonomously handle customer interactions across multiple channels. The system processes inquiries from emails, SMS, WhatsApp, voice calls, and social media, providing intelligent responses, scheduling appointments, sending follow-ups, and managing customer relationships exactly as the business owner would.

**Key Innovation:** 

Unlike generic chatbots, BizClone learns the owner's unique communication style, business policies, pricing, and decision-making patterns through supervised learning, then operates autonomously while maintaining the personal touch that small businesses rely on.

This project combines cutting-edge NLP, speech processing, multi-agent AI systems, calendar integration, and workflow automation to deliver a production-ready MVP.

---

## Project Architecture
```text
bizclone/
│
├── api/                          # FastAPI endpoints (JSON responses)
│   ├── kb_api.py                    # GET /api/kb/manage, POST /api/kb/submit
│   ├── review_api.py                # GET /api/review/queue, /api/review/detail/{id}
│   └── calendar_data_api.py         # GET /api/calendar/data, /api/calendar/booking/{id}
|
├── ui/                              # Frontend routing + static pages
│   ├── home_ui.py                      # Main landing page
│   ├── static_pages_ui.py              # Static HTML serving (client-side rendering)
│   └── templates/                      # Client-rendered HTML pages
│       ├── index.html                  # Home pages
│       ├── kb_manage.html              # KB management (fetch /api/kb/manage)
│       ├── kb_success.html             # KB success confirmation
│       ├── review_form.html            # Email review queue (fetch /api/review/queue)
│       ├── review_email_detail.html    # Individual email review (fetch /api/review/detail/{id})
│       └── calendar.html               # Calendar view (fetch /api/calendar/data)
|
├── database/
│   ├── initial_email_kb.json           # Knowledage base entries for DB initialization
│   ├── customer_initialization.json    # Customer records for DB initialization
│   ├── orm_models.py                   # SQLAlchemy models (6 tables)
│   ├── initialization.py               # DB initialization
│   └── init-db.sql                     # SQL schema
|
├── model/
│   ├── intent_classifier.py              # Intent detection (mixed strategy)
│   ├── intent_classifier_training.ipynb  # Notebook of intent classifier training
│   ├── sample_customer_emails.json       # Training dataset
│   └── intent_classifier_model.pkl       # Saved model  
|     
├── channels/     
│   ├── email/
│   │   ├── birthday_email_service.py   # Automated birthday greetings service
│   │   ├── booking_email_sender.py     # Email sending with iCalendar attachments
│   │   ├── email_agent.py              # End-to-end email orchestrator
│   │   ├── email_history_store.py
│   │   ├── email_watcher.py            # Gmail polling
│   │   ├── gmail_client.py             # Gmail API wrapper
│   │   ├── parser.py                   # Email parsing
│   │   ├── review_store.py             # Escalation queue
│   │   └── urgency_detector.py         # Urgency detector (by emergency keywords) 
│   ├── teams/
│   ├── call/
│   ├── whatsapp/
│   ├── base_watcher.py 
│   └── channel_polling_manager.py
|
├── knowledge_base/
│   ├── learning/                   # KB update + re-index
│   │   ├── feedback_entry.py
│   │   ├── kb_updater.py
│   │   └── learning_mode.py
│   ├── kb_store.py
│   └── vector_index.py
|
├── rag/
│   ├── rag_pipeline.py
│   ├── retriever.py
│   └── vector_store.py
|
├── llm_engine/
│   └── llm_client.py
│
├── scheduling/                     # Birthday/Event scheduler
│   ├── calendar_providers/
│   ├── appointment_workflow.py     # Appointment operations like booking, cancellation, and rescheduling
│   ├── birthday_scheduler.py       # Birthday scheduler  
│   ├── booking_manager.py                     
│   ├── booking_store.py
│   ├── llm_booking_assistant.py
│   ├── scheduler.py
│   └── scheduling_config.py
│
├── config/                         # Configuration
│   ├── google/                     # Goggle account credential files
│   └── config.py                   # Get the global varaibles
│
├── tests/
│
├── main.py                         # FastAPI application entrance
├── requirements.txt
├── docker-compose.yml
├── README.md
└── start-docker.sh                 # Command file to trigger the program
```
---

## Core Capabilities

BizClone implements four main functional areas to automate business operations:

### 1. **Intelligent Email Processing & Response**
- Automatically receives and processes incoming emails from customers
- Classifies customer intent using mixed-strategy engine (TF-IDF + Logistic Regression model)
- Generates intelligent, context-aware replies using RAG (Retrieval-Augmented Generation)
- Escalates complex/urgent emails to business owner for review and approval
- Auto-sends routine responses and sends owner-approved replies via Gmail
- Maintains full email conversation history with threading (via Gmail message_id)

### 2. **Smart Appointment Scheduling**
- Detects appointment-related queries in customer emails
- AI automatically selects best available time slots from owner's calendar
- Generates appointment confirmation emails with iCalendar (.ics) attachments
- Owner can review and modify proposed slots before confirmation
- Integrates with Google Calendar (multi-account support)
- Creates bookings with automatic birthday greetings

### 3. **Knowledge Base Management**
- Centralizes business information: services, pricing, policies, FAQs
- Web interface (`/kb/manage`) for adding and editing KB entries
- Versions all KB updates with audit trail (who changed what and when)
- Automatically indexes KB for RAG retrieval in response generation
- Supports rollback to previous KB versions
- Active/inactive flags ensure only current information is used

### 4. **Owner Review & Control System**
- Web dashboard (`/review`) shows all emails requiring owner approval
- Owner can edit AI-generated replies before sending
- Owner can modify proposed appointment times
- One-click approval sends final email and creates calendar booking
- Audit trail tracks all owner actions and feedback for continuous learning

---

## Email Processing Pipeline

### Overview
The email processing system uses a sophisticated pipeline that separates **intent detection** from **urgency detection**, allowing intelligent escalation of critical emails to the business owner for review while automatically handling routine inquiries.

### Pipeline Workflow

```
Email Arrives
    ↓
Step 1: Parse Email
    ↓
Step 2: Save to History (customer incoming)
    ↓
Step 3: Intent Detection (15 categories)
    ↓
Step 4: Urgency Detection (CRITICAL/HIGH/NORMAL)
    ↓
Step 5: Initialize Response Variables
    ↓
Step 6: Generate Reply (with slot selection for appointments)
    ├─ If appointment-related: Select best time slot via LLM
    └─ Generate reply with context
    ↓
Step 7-8: Decision Logic Based on Urgency
    ├─ If NOT escalated → AUTO-SEND
    │  ├─ Send reply immediately
    │  ├─ If appointment-related: send booking email with .ics
    │  └─ Save Draft Reply to Email_History  ✓
    │
    └─ If escalated → NEEDS OWNER REVIEW
       ├─ Add to Review Queue
       ├─ Owner visits http://localhost:8000/review
       ├─ Owner can:
       │  ├─ Edit reply text
       │  ├─ Modify appointment time (if appointment)
       │  └─ Click "Approve & Send"
       └─ After owner approval:
          ├─ Send final email
          ├─ Save approved reply to history
          ├─ If appointment: create booking with (possibly modified) slot
          └─ Send booking confirmation with .ics  ✓
```


**Email Processing Workflow:**
![Email Processing Workflow](images/email_processing_workflow.png)

### Key Features

| Feature | Description |
|---------|-------------|
| **Dual Decision Logic** | Intent determines reply content; Urgency determines if escalation needed |
| **Appointment Handling** | AI selects best slot, generates reply with context, owner can modify slot before sending |
| **Email History Tracking** | **Auto-save for non-urgent emails**, delayed-save for urgent emails (after owner approval); All emails tracked with `thread_id` and `message_id` for Gmail conversation grouping |
| **Owner Review System** | Escalated emails queue at `/review`, owner can edit reply and/or appointment time before approval |
| **Booking Integration** | Owner-approved appointment emails automatically create calendar bookings with .ics attachments |
| **Gmail Threading** | All replies maintain conversation thread using Gmail's `thread_id` and `message_id` |

---

## Documentation

| Guide | Purpose |
|-------|---------|
| [DOCKER_GUIDE.md](docs/DOCKER_GUIDE.md) | Docker deployment with PostgreSQL |
| [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Complete database design & SQL reference |
| [CHANNEL_INTEGRATION.md](docs/CHANNEL_INTEGRATION.md) | Email, Teams, WhatsApp channel setup |
| [SCHEDULING_SYSTEM.md](docs/SCHEDULING_SYSTEM.md) | Appointment booking system |

---

## API Endpoints

BizClone provides JSON APIs for managing knowledge bases, email reviews, and calendar operations. All endpoints follow REST conventions and return JSON responses.

### Knowledge Base APIs

**`GET /api/kb/manage`** - Get KB field categories
- Returns: JSON object with KB field definitions
- Response: `{"service_category": [...], "policy_type": [...], ...}`

**`POST /api/kb/submit`** - Submit KB update with new entry
- Request: Form data with KB fields (category, value, description, etc.)
- Validates: Field types, required/optional fields via Pydantic
- Response: `{"status": "success", "message": "..."}`
- Errors: 422 for validation errors (returns field-specific error details)

### Email Review APIs

**`GET /api/review/queue`** - Get pending emails for owner review
- Returns: JSON array of escalated emails needing approval
- Response: `[{"id": "...", "from": "...", "subject": "...", "preview": "..."}, ...]`

**`GET /api/review/detail/{email_id}`** - Get full email details
- Returns: Complete email content, generated reply, appointment info (if applicable)
- Response: `{"id": "...", "from": "...", "subject": "...", "body": "...", "reply": "...", "appointment": {...}}`

**`POST /api/review/submit`** - Owner approves/modifies and sends email
- Request: JSON with `email_id`, `reply_text`, optional `appointment_slot` modification
- Action: Sends final email, creates booking (if appointment), updates history
- Response: `{"status": "success", "booking_id": "..."}`

### Calendar APIs

**`GET /api/calendar/data`** - Get calendar grid for month view
- Query params: `year`, `month` (optional, defaults to current)
- Returns: Calendar grid, booked slots, owner availability
- Response: `{"year": 2026, "month": 4, "calendar_days": [[{date, events: []}, ...], ...]}`

**`GET /api/calendar/booking/{booking_id}`** - Get booking details
- Returns: Booking information with customer details and timeslot
- Response: `{"id": "...", "customer_id": "...", "start_time": "...", "status": "..."}`


## Email Channel Input

### Intent Classification System

After model selection, fine-running and training, a sophisticated **mixed-strategy intent classifier** is selected in this project to accurately categorize customer intents:

**TF-IDF + Logistic Regression Classification (hybrid word + character n-grams)** - Strong feature representation; Works very well on high-dimensional sparse text data; Achieved over 85% accuracy.
   - Uses Word n-grams: capture semantic meaning and common phrases
   - Uses Character n-grams: capture subword patterns, spelling variations, prefixes/suffixes, and robustness to noise.

For the model training details, please refer to [intent_classifier_training.ipynb](model/intent_classifier_training.ipynb).

**16 Intent Categories:**
`appointment`, `cancellation`, `price_inquiry`, `complaint`, `refund_request`, `follow_up`, `service_inquiry`, `testimonial`, `availability`, `rescheduling`, `general_inquiry`, `support`, `emergency`, `feedback`, `recommendation`, `other`

### Knowledge Base

The KB consolidates business information for intelligent responses:

- **Services**: Plumbing services with descriptions and hourly rates.
  - Example:     
  ```json
  "toilet_repair": {
      "description": "Repairing flushing issues, leaks, and toilet installation problems.",
      "price": "\u20ac111 per hour"
    }
  ```
- **Policies**: Business operating rules and procedures.
  - Example:     
  ```json
  "payment_methods": "We accept cash, bank transfer, and PayPal after service completion."
  ```

- **FAQs**: Customer frequently asked questions with AI-trained replies.
  - Example:     
  ```json
    {
      "q": "How much does a plumbing repair cost?",
      "a": "Our standard plumbing repair starts at \u20ac80 per hour."
    }
  ```

Stored in `database/initial_email_kb.json` and uploaded to PostgreSQL + ChromaDB on startup for RAG-powered responses.

**Knowledge Base Updating Workflow**
```text
Business Owner edits KB in KB Manage UI
    ↓
Updating table knowledge_base
    ↓
Set updated records is_active=Ture
    ↓
Set old version records is_active=False
```

**Knowledge Base Incert Workflow**
```text
Business Owner create new KB in KB Manage UI
    ↓
Updating table knowledge_base
    ↓
Set updated records is_active=Ture
```


### Database Architecture

**PostgreSQL - 6 Core Tables:**
- **email_history** - Customer email conversations, thread tracking, and message history
- **booking** - Appointment reservations with owner confirmation status
- **knowledge_base** - Versioned knowledge base with active/inactive flags for RAG retrieval
- **kb_feedback** - Audit trail tracking all KB modifications and learning updates
- **customer** - Customer profiles for business operations
- **calendar_account** - OAuth integrations with Google Calendar (multi-account support)

See [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) for full schema details


### Technologies Used
- Programming Language: Python 3.10+
- Backend Framework: FastAPI, Uvicorn
- AI & NLP: TF-IDF + Logistic Regression, Retrieval-Augmented Generation (RAG)
- Vector Database: ChromaDB
- Data Validation & Schemas: Pydantic
- Testing: Pytest, FastAPI TestClient


## Common Modules (Need to Integrate)
- Database
- Knowledge Base
- Rag
- LLM
- Scheduling

## Channel Integration

To integrate a new channel (Teams, WhatsApp, Telegram, etc.) into the multi-channel system:

**See: [CHANNEL_INTEGRATION.md](docs/CHANNEL_INTEGRATION.md)** for complete step-by-step guide.

The guide includes:
- Architecture overview
- Channel component structure
- Step-by-step implementation for new channels
- Response schema requirements
- Testing patterns
- Debugging tips
- Integration checklist

---

## Key System Features

| Feature | Implementation |
|---------|-----------------|
| **Multi-Channel Communication** | Email, Teams, WhatsApp, Calls (extensible channels) |
| **Intelligent Intent Detection** | Mixed strategy (TF-IDF + Logistic Regression) for 16 intent categories |
| **Email Escalation Logic** | Automatic vs. manual review based on urgency detection |
| **Knowledge Base Management** | Versioned KB with UI for adding/editing entries |
| **Appointment Scheduling** | LLM-based slot selection with owner modification |
| **Email Threading** | Gmail message_id tracking for conversation continuity |
| **Calendar Integration** | Multi-account Google Calendar sync with .ics attachments |
| **Owner Review System** | Web interface for approving/modifying escalated emails |
| **Audit Trail** | Full feedback logging of KB modifications |

---

## Quick Start

**PostgreSQL Required** - This application uses PostgreSQL exclusively.

### 1. Configure Environment Varaibles
Before running BizClone, configure these environment variables:

Copy .env.example and rename it as .env file in project root and then edit .env accordingly.

**Example:**
`DATABASE_URL` - PostgreSQL connection string
```bash
DATABASE_URL="postgresql://bizclone_user:password@localhost:5432/bizclone_db"
```

Gmail Authentication:
- `GMAIL_USER` - Gmail account for sending emails
- `GMAIL_APP_PASSWORD` - Gmail app-specific password
- Credentials file: `config/google/credentials.json` (OAuth setup)

### 2. Edit or supplement the data initialization file
Follow the data format of database\customer_initialization.json and database\initial_email_kb.json to modify or supplement them as per your business domain.

customer_initialization.json is related to the birthday greetings function.

initial_email_kb.json is the initial knowledge data. It containes the kb about plumbing business by default. Please change it according to your business.

### 3. Trigger Program
**Option 1: Docker**
Note: It will cost about half hour for the first time to build the images.
```bash
cd bizclone
docker-compose up -d --build
```
Or
```bash
sh start-docker.sh
```
See [DOCKER_GUIDE.md](docs/DOCKER_GUIDE.md) for details

**Option 2: Local Setup**

```bash
# 1. Install PostgreSQL (Windows, Mac, or Linux)
# 2. Create database and user
# 3. Set DATABASE_URL environment variable
# 4. Run: python main.py
```

What Happens Automatically?
- PostgreSQL container starts (port 5433)
- Tables created via SQLAlchemy ORM when app starts
- BizClone API accessible at http://localhost:8000/docs
- All services health-checked
- Data persists in Docker volumes

### Frontend Interfaces

After starting the application, access the owner control panels:

| Interface | URL | Purpose |
|-----------|-----|---------|
| **API Docs** | http://localhost:8000/docs | Swagger UI for all endpoints |
| **Home** | http://localhost:8000/ | Landing page |
| **KB Management** | http://localhost:8000/kb/manage | Add/edit knowledge base entries |
| **Email Review** | http://localhost:8000/review | Review & approve escalated emails |
| **Calendar** | http://localhost:8000/calendar | View appointments and manage scheduling |

**Home website**
![home UI](images/home_ui.png)


**KB Management website**
![KB Management UI](images/KB_Management.png)

**Email Review website**
![Email Review UI](images/email_review.png)

**Calendar website**
![Calendar website](images/calendar_ui.png)



**Frontend Architecture:**
- Client-side rendering with vanilla JavaScript + fetch API
- APIs return JSON, JavaScript dynamically populates HTML templates
- No server-side templating (Jinja2) - pure static file serving
- Real-time form validation and error display

### Verify Installation

After starting the application, verify it's working correctly:

**1. Check API is running**
```bash
curl http://localhost:8000/docs
# Or open in browser: http://localhost:8000/docs
```

**2. Verify database connection**
```bash
docker-compose exec bizclone_app python -c "from database.initialization import init_database; init_database()"
```

**3. Check KB data loaded**
```bash
docker-compose exec bizclone_app python -c \
  "from sqlalchemy import create_engine, text
   import os
   engine = create_engine(os.getenv('DATABASE_URL'))
   with engine.connect() as conn:
       kb_count = conn.execute(text('SELECT COUNT(*) FROM knowledge_base WHERE is_active = TRUE')).scalar()
       booking_count = conn.execute(text('SELECT COUNT(*) FROM booking')).scalar()
       print(f'Active KB records: {kb_count}')
       print(f'Total bookings: {booking_count}')"
```

**4. Test API endpoints**
```bash
# Get KB fields
curl http://localhost:8000/api/kb/manage

# Get email review queue  
curl http://localhost:8000/api/review/queue

# Get calendar data (current month)
curl http://localhost:8000/api/calendar/data
```

**Expected output:**
- API Swagger documentation loads
- Database connection successful
- KB records displayed with proper counts
- All API endpoints return valid JSON responses

After verification, you can:
1. Open http://localhost:8000 in browser (home page)
2. Navigate to KB management at http://localhost:8000/kb/manage
3. Submit test knowledge base entries
4. Review confirmation at http://localhost:8000/kb/success


---

## System Design Principles

**Client-Side Rendering:**
- HTML templates are stateless and served as static files from `ui/templates/`
- JavaScript (vanilla ES6) handles all UI interactions and data fetching
- APIs respond with pure JSON (no templating)
- Benefits: Decoupled frontend/backend, easier testing, better scalability

**API-First Architecture:**
- All data changes go through JSON REST APIs
- FastAPI with Pydantic validation ensures data integrity
- Clear separation between business logic (api/) and presentation (ui/)
- OpenAPI/Swagger docs auto-generated at `/docs`

**Database Design:**
- PostgreSQL with SQLAlchemy ORM for type safety
- 6-table normalized schema without unused tables
- Versioned knowledge base for rollback capability
- Audit trail via kb_feedback table

**Extensibility:**
- New channels can be added following CHANNEL_INTEGRATION.md pattern
- Base classes (BaseWatcher) provide common interface
- Plugins instantiated via ChannelPollingManager
- Zero change required to core email pipeline

---

## Troubleshooting

**Port Already in Use**
```bash
# Check what's using port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Alternative: Run on different port
export UVICORN_PORT=8001
python main.py
```

**Database Connection Error**
```bash
# Verify PostgreSQL is running
docker ps | grep postgres

# Check DATABASE_URL format
echo $DATABASE_URL
# Should be: postgresql://user:password@host:port/database

# Test connection manually
psql $DATABASE_URL -c "SELECT 1"
```

**API Shows "Unhealthy" Status**
```bash
# Wait 15-20 seconds for BERT model to load
# Check logs:
docker-compose logs bizclone_app | tail -20
```

**KB Table Empty After Restart**
```bash
# Full reset (recommended on first run)
docker-compose down -v  # Delete volumes
docker-compose up -d --build  # Fresh start

# This will reload KB records from latest_email_kb.json
```

**Review Queue Shows No Emails**
```bash
# Check if email inbox has unprocessed emails
curl http://localhost:8000/api/review/queue

# Verify email watcher is running
docker-compose logs bizclone_app | grep -i "email\|watcher"

# Check if urgent/escalated emails exist
docker-compose exec bizclone_app psql -U bizclone_user -d bizclone_db \
  -c "SELECT id, from_email, urgency_level FROM email_history ORDER BY created_at DESC LIMIT 5;"
```

**Calendar Shows No Bookings**
```bash
# Test API endpoint directly:
curl http://localhost:8000/api/calendar/data

# Check bookings in database:
docker-compose exec bizclone_app psql -U bizclone_user -d bizclone_db \
  -c "SELECT * FROM booking LIMIT 5;"

# Verify calendar accounts are configured:
docker-compose exec bizclone_app psql -U bizclone_user -d bizclone_db \
  -c "SELECT * FROM calendar_account;"
```

**JavaScript Fetch Errors in Browser**
```bash
# Open browser DevTools (F12) → Console tab
# Common issues:
# 1. API endpoint URL wrong → Check /docs for correct paths
# 2. CORS error → Check FastAPI middleware configuration
# 3. 404 Not Found → Verify endpoint exists (test with curl first)
# 4. 422 Validation → Check request body matches API schema
```

For more details, see [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) and [DOCKER_GUIDE.md](docs/DOCKER_GUIDE.md)

---

### Testing

Run test suite:
```bash
# Test email agent
python -m pytest tests/test_urgency_detector.py -v

# Test intent classification
python -m pytest tests/test_email_intent_classifier.py -v

# All tests
python -m pytest tests/ -v
```

## Project Status

**Current Phase:** Core features operational and tested

**Completed:**
- Email parsing and Gmail integration
- Intent classification (mixed keyword + NLP strategy)
- Email escalation and owner review system
- Knowledge base versioning and management UI
- Appointment scheduling with slot selection
- Calendar integration with Google Calendar  
- Multi-channel architecture foundation
- Database schema optimized (removed unused tables)
- Customer birthday greetings

**In Progress:**
- Teams channel implementation

**Future Work:**
- Design a multi-tenant architecture: allow multiple business owners each with isolated data, KB, and channel configuration.
- Create a real-time dashboard with WebSocket updates instead of page refresh for review queue notifications.
- Advanced RAG optimization
- Performance monitoring dashboard
- User authentication system
- Add an analytics module: email volume by intent, response time distribution, booking conversion rate, urgency escalation rate.
- Implement the customer portal: allow customers to self-serve booking management (view, cancel, reschedule) via a web link.
