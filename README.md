# BizClone - AI-Powered Assistant
This branch will be the final project dev branch with ALL Channels integrated.

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