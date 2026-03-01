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
