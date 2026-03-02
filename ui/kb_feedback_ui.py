from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from knowledge_base.learning.feedback_entry import FeedbackEntry

import requests

router = APIRouter()
templates = Jinja2Templates(directory="ui/templates")


# ----------------------------------
# Knowledge Base Management Page
# ----------------------------------
@router.get("/kb/manage", response_class=HTMLResponse)
def kb_management_page(request: Request):
    """
    Business Owner Knowledge Base Management UI.
    Used to manually insert new KB entries or update existing ones.
    
    Operations:
    - INSERT: Add completely new knowledge (service, policy, FAQ)
    - UPDATE: Correct or modify existing knowledge based on customer feedback
    """
    KB_FIELDS = FeedbackEntry.get_kb_fields()
    return templates.TemplateResponse(
        "kb_manage.html",
        {"request": request, "kb_fields": KB_FIELDS}
    )


# ----------------------------------
# Submit KB Update or Insert
# ----------------------------------
@router.post("/kb/submit", response_class=HTMLResponse)
def submit_kb_update(
    request: Request,
    kb_field: str = Form(...),
    operation: str = Form(...),
    customer_question: str = Form(None),
    owner_correction: str = Form(None),
    service_name: str = Form(None),
    service_description: str = Form(None),
    service_price: str = Form(None),
):
    """
    Owner manually updates existing knowledge or inserts new knowledge
    into the system KB.
    
    For UPDATE/INSERT Service: service_name, service_description, service_price are used
    For UPDATE/INSERT Policy/FAQ: customer_question, owner_correction are used
    """
    kb_entry = FeedbackEntry(
        customer_question=customer_question,
        owner_correction=owner_correction,
        service_name=service_name,
        service_description=service_description,
        service_price=service_price,
        kb_field=kb_field,
        operation=operation
    )

    api_url = "http://localhost:8000/learning/feedback"

    response = requests.post(api_url, json=kb_entry.model_dump(mode="json"))

    if response.status_code != 200:
        return HTMLResponse(
            f"<h2>Error updating KB</h2><pre>{response.text}</pre>",
            status_code=500
        )

    result = response.json()

    return templates.TemplateResponse(
        "kb_success.html",
        {"request": request, "result": result}
    )
