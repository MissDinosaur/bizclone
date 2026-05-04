from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import logging

from channels.email.review_store import get_review_context, clear_review_context
from channels.email.gmail_client import GmailClient
from knowledge_base.email_history_store import EmailHistoryStore

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="ui/templates")

gmail = GmailClient()
email_store = EmailHistoryStore()


@router.get("/review", response_class=HTMLResponse)
def review_page(request: Request):
    """
    Display pending emergency email for review.
    """

    data = get_review_context()

    if not data:
        return HTMLResponse("<h2>No emergency emails pending review.</h2>")

    return templates.TemplateResponse(
        "review_form.html",
        {"request": request, "data": data}
    )


@router.post("/review/submit", response_class=HTMLResponse)
def submit_review(
    request: Request,
    customer_email: str = Form(...),
    customer_question: str = Form(...),
    agent_reply: str = Form(...),
    owner_correction: str = Form(""),
    subject: str = Form(...),
    thread_id: str = Form(...),
    message_id: str = Form(...)
):
    """
    Owner approves or edits AI-generated emergency reply.
    
    Handles data consistency:
    - Updates email_history with final reply (whether corrected or not)
    """

    corrected_reply = owner_correction.strip()
    final_reply = corrected_reply if corrected_reply else agent_reply

    try:
        # Send final email via Gmail
        gmail.send_email_reply(
            to_email=customer_email,
            subject=subject,
            body=final_reply,
            thread_id=thread_id,
            message_id=message_id
        )
        logger.info(f"Emergency email sent to {customer_email}")
        
        # UPDATE: Record the final reply that was actually sent
        if corrected_reply != "" and corrected_reply != agent_reply.strip():
            logger.info(f"Owner correction made for {customer_email}. Updating email history with final reply.")
            email_store.update_email_reply(
                customer_email=customer_email,
                subject=subject,
                updated_reply=corrected_reply
            )
            logger.debug(f"Updated email_history with final reply for {customer_email}")
        
        clear_review_context()
        return HTMLResponse("<h2>Emergency email sent successfully.</h2>")
        
    except Exception as e:
        logger.error(f"Error in submit_review: {str(e)}", exc_info=True)
        return HTMLResponse(
            f"<h2>Error sending emergency email: {str(e)}</h2>",
            status_code=500
        )
