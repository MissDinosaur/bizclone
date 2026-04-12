"""
Static Pages UI Router - Provides HTML pages without server-side rendering.
All HTML pages are now client-side rendered with data fetched from API endpoints via JavaScript.

Pages:
- /kb/manage - Knowledge Base Management page
- /kb/success - KB submission success page  
- /review - Email Review Queue page
- /review/<email_id> - Email Detail page
- /calendar - Calendar page
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Knowledge Base Management Pages
@router.get("/kb/manage")
def kb_manage_page():
    """
    Knowledge Base Management page.
    HTML contains JavaScript that:
    1. Fetches KB fields from /api/kb/manage
    2. Submits updates to /api/kb/submit
    3. Handles validation and error display on client-side
    """
    return FileResponse(
        "ui/templates/kb_manage.html",
        media_type="text/html"
    )


@router.get("/kb/success")
def kb_success_page():
    """
    KB submission success page.
    """
    return FileResponse(
        "ui/templates/kb_success.html",
        media_type="text/html"
    )


# Email Review Pages
@router.get("/review")
def review_queue_page():
    """
    Email review queue page.
    HTML contains JavaScript that:
    1. Fetches pending emails from /api/review/queue
    2. Dynamically renders email cards
    3. Navigates to detail page on email click
    """
    return FileResponse(
        "ui/templates/review_form.html",
        media_type="text/html"
    )


@router.get("/review/{email_id}")
def review_email_detail_page(email_id: int):
    """
    Individual email detail page for review.
    HTML contains JavaScript that:
    1. Fetches email details from /api/review/detail/{email_id}
    2. Renders form with customer/AI messages
    3. Submits review to /api/review/submit
    4. Auto-redirects to /review after successful submission
    """
    return FileResponse(
        "ui/templates/review_email_detail.html",
        media_type="text/html"
    )


# Calendar Pages
@router.get("/calendar")
def calendar_page():
    """
    Booking calendar page.
    HTML contains JavaScript that:
    1. Fetches calendar data from /api/calendar/data?month=X&year=Y
    2. Dynamically renders calendar grid
    3. Supports month navigation
    4. Fetches booking details from /api/calendar/booking/{booking_id}
    """
    return FileResponse(
        "ui/templates/calendar.html",
        media_type="text/html"
    )
