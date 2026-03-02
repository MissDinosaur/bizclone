# bizclone

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
└── tests/
│   └── test_email_agent.py
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
