# BizClone - AI-Powered Assistant
Please follow the project architecture in this branch to integrate your channel parts.

Please refer to docs\CHANNEL_INTEGRATION.md for a better understanding.
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
├── api/
│   └── kb_learning_api.py        # api of KB updates
|
├── ui/
│   ├── templates/
│   ├── review_email_ui.py
│   └── kb_feedback_ui.py
|
├── database/
│   ├── orm_models.py
│   ├── initialization.py
│   └── initial_email_kb.json
|
├── channels/
│   ├── email/
│   │   └── email_agent.py          # End-to-end orchestrator of emial agent
│   ├── teams/
│   ├── call/
│   ├── facebook/
│   ├── whatsup/
│   ├── base_watcher.py 
│   └── channel_polling_manager.py
|
├── knowledge_base/
│   ├── learning/                # KB update + re-index
│   ├── email_history_store.py
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
│── scheduling/                  # Shared appointment integration layer
│   ├── booking_store_db.py
│   ├── scheduling_config.py
│   └── scheduler.py
│
│── tests/
│
├── main.py                       # Program entrance
├── requirements.txt
└── README.md
```


## Documentation

| Guide | Purpose |
|-------|---------|
| [DOCKER_GUIDE.md](DOCKER_GUIDE.md) | Docker deployment with PostgreSQL |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Complete database design & SQL reference |
| [CHANNEL_INTEGRATION.md](CHANNEL_INTEGRATION.md) | Email, Teams, WhatsApp channel setup |
| [SCHEDULING_SYSTEM.md](scheduling/SCHEDULING_SYSTEM.md) | Appointment booking system |


## Channel Input

### Knowledge Base
The KB was expanded to over 100 structured entries to improve retrieval coverage and response quality in the RAG pipeline.

The Knowledge Base consolidates business information for intelligent responses:

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

### 1. Email Agent Pipeline

**Email Processing Flow:**
```
Customer Email
    ↓
Email Parser
    ↓
Intent Classification + Urgency Detection
    ↓
Retrieve Conversation History (from PostgreSQL)
    ↓
Query Knowledge Base (PostgreSQL + ChromaDB)
    ↓
Generate LLM Response with Context (Intent + Email + Email history + KB)
    ↓ If Normal Case             ↓ If Emergenct Case
    ↓                  Owner Review & Approval
    ↓                            ↓
Send Reply via Gmail or Calendar Booking
    ↓
Store in Database
```

### Database Architecture

**4 PostgreSQL Tables:**
- **email_history** - Customer conversations & email context
- **booking** - Appointment bookings (multi-channel)
- **knowledge_base** - Knowledge base versions with active KB cache (consolidated from kb_version + kb_current)
- **kb_feedback** - Audit trail of KB modifications

See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for full schema details


### Technologies Used
- Programming Language: Python 3.10+
- Backend Framework: FastAPI, Uvicorn
- AI & NLP: SentenceTransformers, Retrieval-Augmented Generation (RAG)
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

**See: [CHANNEL_INTEGRATION.md](./CHANNEL_INTEGRATION.md)** for complete step-by-step guide.

The guide includes:
- Architecture overview
- Channel component structure
- Step-by-step implementation for new channels
- Response schema requirements
- Testing patterns
- Debugging tips
- Integration checklist

---

## Quick Start

**PostgreSQL Required** - This application uses PostgreSQL exclusively.

### 1. Configure Environment Varaibles
Before running BizClone, configure these environment variables:

Copy .env.example and rename as .env file in project root and then edit .env accordingly.

**Example:**
`DATABASE_URL` - PostgreSQL connection string
```bash
DATABASE_URL="postgresql://bizclone_user:password@localhost:5432/bizclone_db"
```

Optional (Gmail, Teams integration):
- `GMAIL_USER` - Gmail account for sending emails
- `GMAIL_APP_PASSWORD` - Gmail app-specific password
- Credentials file: `config/gmail/credentials.json` (OAuth setup)


### 2. Trigger Program
**Option 1: Docker**
```bash
cd bizclone
docker-compose up -d --build
# or sh start-docker.sh
```
See [DOCKER_GUIDE.md](DOCKER_GUIDE.md) for details

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
---

### Verify Installation

After starting the application, verify it's working correctly:

```bash
# 1. Check API is running
curl http://localhost:8000/docs

# 2. Verify database connection
docker-compose exec bizclone_app python -c "from database.initialization import init_database; init_database()"

# 3. Check KB data loaded (should show 65 records)
docker-compose exec bizclone_app python -c \
  "from sqlalchemy import create_engine, text
   import os
   engine = create_engine(os.getenv('DATABASE_URL'))
   with engine.connect() as conn:
       result = conn.execute(text('SELECT COUNT(*) FROM knowledge_base WHERE is_active = TRUE'))
       print(f'Active KB records: {result.scalar()}')"
```

Expected output:
- API responds with Swagger documentation
- Database connection successful
- 65 knowledge base records loaded

After program is triggered, the Owner can open:
- **Feedback UI** (KB Management): http://localhost:8000/feedback
- **Email Review UI** (Emergency emails): http://localhost:8000/review
- **API Documentation**: http://localhost:8000/docs

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

# This will reload all 65 KB records from latest_email_kb.json
```

**Forms Not Submitting**
```bash
# Check browser console for errors (F12)
# Ensure required fields are filled
# Verify database is accepting writes
docker exec bizclone_app psql -U bizclone_user -d bizclone_db -c "SELECT * FROM kb_feedback LIMIT 1;"
```

For more details, see [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) and [DOCKER_GUIDE.md](DOCKER_GUIDE.md)