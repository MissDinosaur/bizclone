# BizClone — AI Voice Assistant for Plumbing Business

**An intelligent, automated voice assistant system for small enterprise plumbing services in Hamburg, Germany.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://www.postgresql.org/)
[![Celery](https://img.shields.io/badge/Celery-5.3.6-green.svg)](https://docs.celeryproject.org/)

---

## 🎯 Overview

BizClone is an AI-powered voice assistant that automates customer call handling for plumbing businesses. The system processes recorded audio files, transcribes speech, classifies intent, extracts entities, and manages appointments (book, cancel, reschedule) — all without human intervention.

### Key Capabilities

| Capability | Description |
|---|---|
| **Transcription** | OpenAI Whisper — converts call recordings to text |
| **Intent Classification** | GPT-4o-mini / Groq Llama 3 — 7 intent categories |
| **Entity Extraction** | GPT-4o-mini — 8 entity types (name, phone, date, service, …) |
| **Smart Scheduling** | Automatic booking with business-hours & conflict checks |
| **Cancel / Reschedule** | Voice-driven appointment modification via API |
| **Google Calendar** | Creates, updates, and deletes events on a target calendar |
| **Priority Detection** | Urgency scoring (0-100) with emergency flagging |
| **Knowledge Base** | RAG-powered FAQ retrieval with ChromaDB |
| **Admin UI** | Jinja2 dashboard for services, FAQs, and daily reports |

---

## ✨ Features

### Call Processing Pipeline
- FastAPI backend with health monitoring
- PostgreSQL database with SQLAlchemy ORM
- Celery task queue with Redis broker
- OpenAI Whisper transcription (local model)
- Structured logging with `structlog`

### AI Intelligence
- GPT-4o-mini intent classification (7 categories)
- Entity extraction (8 entity types)
- Priority detection and scoring (0-100)
- Conversation state management
- ChromaDB vector database for RAG
- Business knowledge base (50+ FAQs)

### Scheduling & Calendar
- Intelligent appointment booking
- Business hours validation (08:00–18:00)
- Conflict detection with auto-rescheduling
- Google Calendar integration (create / update / delete events)
- Appointment cancellation and rescheduling via API

### Admin & Reporting
- Admin dashboard (`/admin/`) with stats overview
- Service management (add / edit / delete)
- FAQ management (add / edit / delete)
- Daily summary reports (`/admin/reports`, `/reports/daily`)

---

## 🏗️ Architecture

```
 Recording (WAV/MP3)
        │
        ▼
 ┌──────────────────────┐
 │  Audio File Storage   │   data/recordings/
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  Whisper Transcription│   Celery task
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  Intent Classification│   GPT-4o-mini / Groq
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  Entity Extraction    │   GPT-4o-mini
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  Scheduling / Cancel  │   Google Calendar sync
 │  / Reschedule         │
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  PostgreSQL + Logs    │
 └──────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Framework** | FastAPI 0.109 · Uvicorn · Python 3.11+ |
| **Database** | PostgreSQL 15+ · SQLAlchemy 2.0 · Alembic |
| **Task Queue** | Celery 5.3 · Redis |
| **AI / ML** | OpenAI GPT-4o-mini · Groq Llama 3 · Whisper (local) |
| **Vector DB** | ChromaDB · sentence-transformers |
| **Calendar** | Google Calendar API (service account) |
| **Frontend** | Jinja2 templates · vanilla CSS |
| **Logging** | structlog (JSON in prod, console in dev) |
| **Testing** | pytest · pytest-cov |

---

## 📁 Project Structure

```
BizClone/
├── backend/
│   ├── app/
│   │   ├── api/                # Routers (health, n8n, calendar, admin, reports, system)
│   │   ├── config/             # Settings (pydantic-settings)
│   │   ├── core/               # Logging, exceptions, middleware, business data loader
│   │   ├── db/                 # Session, CRUD helpers
│   │   ├── models/             # SQLAlchemy models (Customer, Call, Appointment, …)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── ai/             # Intent classifier, entity extractor, response generator
│   │   │   ├── integrations/   # Google Calendar client
│   │   │   ├── scheduling/     # Scheduler, cancel, reschedule services
│   │   │   ├── reporting/      # Daily summary generator
│   │   │   ├── voice/          # Whisper transcription, audio handler
│   │   │   └── rag/            # ChromaDB knowledge base
│   │   ├── static/css/         # Admin UI stylesheet
│   │   ├── templates/          # Jinja2 HTML templates
│   │   └── workers/            # Celery tasks (chained pipeline)
│   ├── tests/                  # Unit & integration tests
│   ├── migrations/             # Alembic migration versions
│   └── process_recording.py    # CLI for processing audio files
├── data/
│   ├── recordings/             # Input audio files (WAV / MP3)
│   ├── transcripts/            # Generated transcripts
│   └── chroma/                 # Vector store persistence
├── documentation/              # Project docs
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # PostgreSQL + Redis
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (PostgreSQL + Redis)
- OpenAI API key
- Google Calendar service-account JSON (optional)

### Setup

```bash
# 1. Clone & virtualenv
git clone <repository-url> && cd BizClone
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env   # Edit: OPENAI_API_KEY, DATABASE_URL, REDIS_URL

# 3. Start infrastructure
docker-compose up -d

# 4. Migrate & seed
cd backend
alembic upgrade heads

# 5. Run
uvicorn app.main:app --reload --port 8000          # Terminal 1
celery -A app.workers.celery_app worker --loglevel=info  # Terminal 2
```

### Verify

```bash
curl http://localhost:8000/health
open http://localhost:8000/docs      # Swagger UI
open http://localhost:8000/admin/    # Admin dashboard
```

---

## 🎙️ Processing Recordings

```bash
cd backend

# Process a single recording
python process_recording.py --file ../data/recordings/call_01.wav

# With custom caller number
python process_recording.py --file ../data/recordings/call_01.wav \
    --customer-phone "+491234567890"
```

The Celery pipeline automatically runs: **Transcription → Intent → Entities → Scheduling → Google Calendar**.

---

## 🔗 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/webhooks/n8n/voice` | Upload recording for processing |
| `GET` | `/calendar/appointments` | List appointments |
| `POST` | `/calendar/appointments/cancel` | Cancel an appointment |
| `POST` | `/calendar/appointments/reschedule` | Reschedule an appointment |
| `GET` | `/reports/daily` | Daily summary (JSON) |
| `GET` | `/admin/` | Admin dashboard |
| `GET` | `/admin/services` | Manage services |
| `GET` | `/admin/faqs` | Manage FAQs |
| `GET` | `/admin/reports` | Reports page |

---

## 🧪 Testing

```bash
cd backend
pytest -v                              # All tests
pytest tests/test_cancel_reschedule.py  # Cancel/reschedule tests
pytest --cov=app --cov-report=html     # With coverage
```

---

## 📚 Documentation

| Document | Description |
|---|---|
| [WEEK3_COMPLETE.md](documentation/WEEK3_COMPLETE.md) | Full feature summary |
| [PROJECT_STRUCTURE.md](documentation/PROJECT_STRUCTURE.md) | Detailed project structure |
| [RECORDING_PROCESSING.md](documentation/RECORDING_PROCESSING.md) | Recording processing guide |
| [QUICK_DEMO_GUIDE.md](documentation/QUICK_DEMO_GUIDE.md) | Demo walkthrough |
| [QUICK_START.md](documentation/QUICK_START.md) | Quick start guide |
| [TROUBLESHOOTING.md](documentation/TROUBLESHOOTING.md) | Common issues & fixes |

---

## 📞 Business Configuration

| Setting | Value |
|---|---|
| Business Name | QuickFix Plumbing |
| Location | Hamburg, Germany |
| Business Hours | Mon–Fri, 08:00–18:00 |
| Target Calendar | `21sspd@gmail.com` |
| Appointment Duration | 60 min (+ 15 min buffer) |

---

## 📄 License

This project was developed as a case study for the MSc ADSA programme.