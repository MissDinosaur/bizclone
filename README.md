# bizclone
1. Project Introduction 
Small enterprises—plumbers, mechanics, consultants, tutors, salon owners, and other service providers—face a critical challenge: managing customer communications and scheduling while delivering hands-on services. With limited staff and budget, these business owners often struggle to respond promptly to inquiries, manage appointments, and maintain consistent customer service quality. 

This project aims to develop "BizClone" - an AI-powered digital assistant that learns from a business owner's communication patterns, scheduling preferences, and service offerings to autonomously handle customer interactions across multiple channels. The system will process inquiries from emails, SMS, WhatsApp, voice calls, and social media, providing intelligent responses, scheduling appointments, sending follow-ups, and managing customer relationships exactly as the business owner would. 

**Key Innovation:** Unlike generic chatbots, BizClone learns the master's unique 
communication style, business policies, pricing, and decision-making patterns through a supervised learning phase, then operates autonomously while maintaining the personal touch that small businesses rely on. 
This project combines cutting-edge NLP, speech processing, multi-agent AI systems, 
calendar integration, and workflow automation to deliver a production-ready MVP that can be marketed to small enterprises.
### bizclone-email-agent
A complete Email Agent microservice with its own knowledge base and retrieval system.

The assistant learns the business owner’s style and policies, then autonomously handles customer interactions across channels.

This task is to build one complete agent pipeline:

Incoming Email → Emails Parser → Intent Detection → Email Knowledge Base → RAG Retrieval → LLM Response Draft

Gmail Inbox → Email Agent → Router → KB/RAG → Response → Send back via Gmail



#### Workflow:
```text
Incoming Email
     ↓
Email Parser
     ↓
Intent Detection
     ↓
Email Knowledge Base (JSON + Vector DB)
     ↓
RAG Retrieval
     ↓
LLM Response Draft
     ↓
Calendar Booking / Follow-up
     ↓
Feedback → KB Version Update
```

```text
Customer Email arrives
    ↓
✓ Save to database (customer, subject, body)
    ↓
Detect intent
    ↓
✓ Retrieve last 5 emails from this customer (from database)
    ↓
Generate LLM prompt with:
  - Previous conversation context
  - KB documents
  - Current email
    ↓
Generate reply (with full context awareness)
    ↓
✓ Save reply to database (our response, intent)
```


- Gmail API integration (read/send skeleton)
- Email normalization + parsing
- Intent classification
- Email-specific Knowledge Base ingestion
- RAG retrieval with ChromaDB
- Calendar booking mock
- FastAPI endpoint /email/process
- Demo script
- Test skeleton
- Integration-ready architecture

#### Technologies Used
- Programming Language: Python 3.10+
- Backend Framework: FastAPI, Uvicorn
- AI & NLP: SentenceTransformers, Retrieval-Augmented Generation (RAG)
- Vector Database: ChromaDB
- Data Validation & Schemas: Pydantic
- Testing: Pytest, FastAPI TestClient

**Knowledge Update Workflow**
Business Owner edits KB JSON
        ↓
KB Validator checks schema
        ↓
KB Version increment (v1 → v2)
        ↓
Vector Index Rebuild
        ↓
RAG uses new knowledge immediately



In Learning Mode, owner corrections are applied directly into structured KB fields such as service pricing and business policies.

The system then automatically re-indexes the vector database, ensuring RAG responses reflect the latest business knowledge.


A simple Feedback UI instantly makes Learning Mode look like a real product:
- Owner corrects KB
- KB updates + vector DB rebuild
- Future answers improve

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
│   ├── ingestion.py
│   ├── kb_manager.py
│   └── vector_index.py
|
├── rag/
│   ├── rag_pipeline.py
│   ├── retriever.py
│   └── vector_store.py
|
├── data/
│   ├── chroma_email_db/          # Email agent vector DB
│   └── kb/
│   │   ├── updates/
│   │   ├── versions/
│   │   └── latest_email_kb.json
|
├── llm_engine/
│   └── llm_client.py
│
│── scheduling/                  # Shared appointment integration layer
│   └── scheduler.py
│
│── tests/
│
├── main.py                       # Program entrance
├── requirements.txt
└── README.md
```

| Component    | Endpoint             | Purpose                |
| ------------ | -------------------- | ---------------------- |
| Email Agent  | Background thread    | Auto-reply emails      |
| Learning API | `/learning/feedback` | KB update + re-index   |
| Feedback UI  | `/feedback`          | Owner supervision demo |


## Set up
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <project-folder-name>
   ```

2. Create a virtual environment named <venvName> (Recommended Python version==3.10.0 or 3.11.0):
   ```bash
   python -m venv <venvName>  # Replace <venvName> by your venv name 
   ```

3. Activate the virtual environment <venvName>:
   ```bash
   # Replace <venvName> by your venv name 

   # Windows (CMD/Powershell)
   <venvName>\Scripts\activate

   # Windows (git bash)
   source <venvName>/Scripts/activate

   # macOS/Linux
   source <venvName>/bin/activate

   # if you wanna quit the current virtual environment
   deactivate
   ```

4. Install the dependencies (Recommended Python version==3.10.0 or 3.11.0):
   ```bash
   pip install -r requirements.txt
   ```

5. Configuration: All sensitive configurations are managed in `.env` file:
    ```bash
    # Copy template to create your own
    cp .env.example .env
    ```

6. Run the command to trigger the program
    ```bash
    uvicorn main:app --reload
    ```
    After program is triggered, the Owner can open:
    - **Feedback UI** (KB Management): http://localhost:8000/feedback
    - **Email Review UI** (Emergency emails): http://localhost:8000/review
    - **API Documentation**: http://localhost:8000/docs


## API Schemas
All channel responses (Email, Teams, WhatsApp, Call, Facebook) follow a unified Pydantic schema:

```json
{
  "channel": "email",
  "status": "auto_send",
  "intent": "appointment_booking_request",
  "reply": "Your scheduled appointment for March 5 at 10:00 AM...",
  "booking": {
    "id": "BK20260302100000001",
    "slot": "2026-03-05 10:00",
    "customer_email": "customer@example.com",
    "status": "confirmed"
  },
  "error_code": null,
  "error_message": null
}
```

**Status Values:**
- `auto_send` - Ready to send automatically
- `needs_review` - Requires owner review (emergency cases)
- `failed` - Processing failed

**Intent Types:**
- `pricing_inquiry`
- `appointment_booking_request`
- `cancellation_request`
- `business_hours_question`
- `emergency_service_request`
- `general_faq_question`

## Email History & Context-Aware Responses

The system now stores email conversation history to provide LLM with **customer context** for more personalized replies.

### How It Works

1. **Incoming Email Saved**: Customer emails are stored in the database with:
   - Customer email address (for grouping)
   - Subject and body
   - Detected intent
   - Timestamp

2. **Previous Interactions Retrieved**: When generating replies, the system retrieves the last 5 emails from that customer

3. **Enhanced LLM Prompt**: Previous conversation history is included in the LLM prompt, allowing it to:
   - Reference prior interactions
   - Maintain conversation continuity
   - Provide more personalized responses
   - Understand customer history and patterns

4. **Our Reply Saved**: Generated replies are also saved to history for future reference

### Database Configuration

The system uses **SQLAlchemy ORM** for flexible database management:

**Development (Default):**
```bash
DATABASE_URL=sqlite:///data/bizclone.db
```
- File-based SQLite database
- No external setup required
- Automatically created on first run
- Located in `data/bizclone.db`

**Production:**
```bash
DATABASE_URL=postgresql://user:password@host:5432/bizclone
```
- Switch to PostgreSQL for multi-instance deployments
- Same code works with just connection string change (thanks to SQLAlchemy)

### Database Schema

**EmailHistory Table:**
```sql
CREATE TABLE email_history (
    id INTEGER PRIMARY KEY,
    customer_email VARCHAR(255),
    timestamp DATETIME,
    sender VARCHAR(255),
    subject VARCHAR(512),
    body TEXT,
    our_reply TEXT,
    intent VARCHAR(100),
    channel VARCHAR(50)
)
```

### Email History Store API

```python
from knowledge_base.email_history_store import EmailHistoryStore

store = EmailHistoryStore()

# Save incoming email
store.save_email(
    customer_email="customer@example.com",
    sender="customer",
    subject="Question about services",
    body="...",
    intent="pricing_inquiry",
    channel="email"
)

# Retrieve conversation history (for LLM context)
history = store.get_customer_history(
    customer_email="customer@example.com",
    limit=5
)

# Get formatted text for LLM prompt
prompt_context = store.get_conversation_for_prompt(
    customer_email="customer@example.com"
)

# Get database statistics
stats = store.get_database_stats()
print(f"Total emails: {stats['total_emails']}")
print(f"Unique customers: {stats['unique_customers']}")
```

### RAG Pipeline with History Context

The RAG pipeline now includes email history in prompts to provide context:

```python
reply_text, kb_docs = rag_pipeline.generate_email_reply(
    customer_email="customer@example.com",
    intent="pricing_inquiry",
    booking=booking_info
)
```

The prompt now includes:
- Last 5 emails from this customer
- Previous replies to similar questions
- Customer communication history
