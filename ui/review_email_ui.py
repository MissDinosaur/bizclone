from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from channels.email.review_store import get_review_context, clear_review_context
from channels.email.gmail_client import GmailClient
import requests

router = APIRouter()
templates = Jinja2Templates(directory="ui/templates")

gmail = GmailClient()


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
    Owner approves or edits emergency draft.
    """

    final_reply = owner_correction.strip() if owner_correction.strip() else agent_reply

    # Send final email
    gmail.send_email_reply(
        to_email=customer_email,
        subject=subject,
        body=final_reply,
        thread_id=thread_id,
        message_id=message_id
    )
    # If modified → update KB
    # if owner_correction.strip():
    #     requests.post(
    #         "http://localhost:8000/learning/feedback",
    #         json={
    #             "customer_question": customer_question,
    #             "agent_reply": agent_reply,
    #             "owner_correction": owner_correction,
    #             "intent": intent,
    #             "kb_field": kb_field
    #         }
    #     )

    clear_review_context()

    return HTMLResponse("<h2>Emergency email sent successfully.</h2>")
