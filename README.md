BizClone – Facebook Agent (dev_facebook branch)

Overview

This branch introduces a fully functional Facebook Messenger automation system with:
	•	Webhook integration (Meta Graph API)
	•	AI-assisted intent detection
	•	Multi-step booking flow
	•	Pricing flow with Knowledge Base (DB-backed)
	•	Conversation state management
	•	Structured logging

⸻

Features

1. Booking Flow

Supports:
	•	“schedule a visit”
	•	“tomorrow morning”
	•	“Tuesday 13:00”

Flow:
	1.	Ask for day
	2.	Ask for time (morning/afternoon)
	3.	Suggest alternatives if unavailable
	4.	Accept explicit slot selection
	5.	Confirm booking

⸻

2. Pricing Flow

Supports:
	•	“price?”
	•	“how much will it cost?”
	•	“plumbing”
	•	“leak repair”

Behavior:
	•	Detects service name
	•	Stores last service in conversation state
	•	Fetches pricing from knowledge_base table
	•	Falls back to generic response if not found

⸻

3. Conversation State

Stored in conversation_state table:

Fields:
	•	last_intent
	•	awaiting_pricing_service
	•	awaiting_booking_details
	•	state_data (JSON)

Enables:
	•	multi-turn conversations
	•	memory across messages

⸻

4. AI Integration

Uses OpenAI:
	•	Model: gpt-4o-mini
	•	Used for:
	•	intent classification
	•	fallback replies

⚠️ Requires valid API key:

OPENAI_API_KEY=your_real_key


⸻

5. Logging

Replaced all print() calls with structured logging:

Example:

[INFO] [FACEBOOK] Processing message...


⸻

Setup

1. Environment variables

OPENAI_API_KEY=...
META_PAGE_ACCESS_TOKEN=...
META_VERIFY_TOKEN=...
DATABASE_URL=postgresql://...


⸻

2. Run server

python -m uvicorn main:app


⸻

3. Test flow

Example:

User: hi
Bot: Hello! How can I assist you today?

User: can you book me for tomorrow morning?
Bot: No available morning slots for tomorrow. Nearest available options: Tuesday 13:00...

User: Tuesday 13:00
Bot: Your booking is confirmed...


⸻

Git Workflow

Branch:

dev_facebook

Push:

git push origin dev_facebook

Create PR:

https://github.com/MissDinosaur/bizclone/pull/new/dev_facebook


⸻

Next Steps
	•	Instagram channel integration
	•	Better service extraction (NLP)
	•	KB semantic search (vector-based)
	•	Admin dashboard

⸻

Status

✅ Production-ready MVP for Facebook Messenger automation