from fastapi import FastAPI

# Email agent core
from channels.email.email_agent import process_email
from channels.email.email_watcher import EmailWatcher

from api.kb_learning_api import router as learning_router
from ui.kb_feedback_ui import router as feedback_ui_router
from ui.review_email_ui import router as review_router


app = FastAPI(title="BizClone Email Agent MVP")

# -----------------------------
# Background Gmail Polling Agent
# -----------------------------
watcher = EmailWatcher(poll_interval=300)

@app.on_event("startup")
def startup_event():
    """
    When FastAPI launches:
    start Gmail polling in background thread.
    """
    watcher.start()

# -----------------------------
# Manual Email Processing Endpoint
# -----------------------------
@app.post("/email/process")
def process_google_email(payload: dict):
    """
    Manual endpoint for testing one email payload.
    """
    return process_email(payload)

# -----------------------------
# Include routers
# -----------------------------
app.include_router(learning_router)       # Core Learning API, updating KB
app.include_router(feedback_ui_router)    # Owner Feedback UI
app.include_router(review_router)

""""
Full Runtime Flow (End-to-End)
After run: uvicorn app.main:app --reload
Step 1 — FastAPI Server Starts
Step 2 — Startup Event and Watcher are Triggered
Step 3 — If Customer Sends Email then Watcher Detects New Email
Step 5 — Email Parsed
Step 5 — Email Parsed
Step 7 — Knowledge Base Retrieval (RAG): JSON KB chunking, JSON KB chunking
Step 8 — LLM Draft Response: Prompt = Email + Email Intent + Retrieved KB Context
Step 9 — Agent Sends Email Back

Learning Mode Runs in Parallel
The Owner can open Feedback UI Page: http://localhost:8000/feedback
Owner Submits Correction
KB Updated Structurally
Next Email Uses Updated Knowledge Base
"""