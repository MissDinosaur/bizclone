"""
Admin UI routes — Jinja2 server-side rendered pages for knowledge base management.
"""
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.crud import (
    get_all_services, get_service_by_id, create_or_update_service, delete_service,
    get_all_faqs, get_faq_by_id, create_or_update_faq, delete_faq,
    list_calls, list_appointments,
)
from app.services.reporting.daily_summary import generate_daily_summary
from app.core.logging import get_logger

logger = get_logger(__name__)

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(prefix="/admin", tags=["Admin UI"])


# ─── Dashboard ───────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    services = get_all_services(db)
    faqs = get_all_faqs(db)
    calls = list_calls(db, limit=500)
    appointments = list_appointments(db, limit=10)
    stats = {
        "total_services": len(services),
        "total_faqs": len(faqs),
        "total_calls": len(calls),
        "total_appointments": len(list_appointments(db, limit=10000)),
    }
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "active": "dashboard",
        "stats": stats, "recent_appointments": appointments,
    })


# ─── Services ────────────────────────────────────────────────────────────────

@router.get("/services", response_class=HTMLResponse)
def services_list(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("services.html", {
        "request": request, "active": "services",
        "services": get_all_services(db),
    })


@router.get("/services/new", response_class=HTMLResponse)
def service_new(request: Request):
    return templates.TemplateResponse("service_form.html", {
        "request": request, "active": "services", "service": None,
    })


@router.get("/services/{service_id}/edit", response_class=HTMLResponse)
def service_edit(request: Request, service_id: int, db: Session = Depends(get_db)):
    svc = get_service_by_id(db, service_id)
    return templates.TemplateResponse("service_form.html", {
        "request": request, "active": "services", "service": svc,
    })


@router.post("/services/create")
def service_create(
    service_key: str = Form(...), name: str = Form(...),
    description: str = Form(...), price: str = Form(...),
    db: Session = Depends(get_db),
):
    create_or_update_service(db, service_key, name, description, price)
    logger.info("admin_service_created", service_key=service_key)
    return RedirectResponse("/admin/services", status_code=303)


@router.post("/services/update/{service_id}")
def service_update(
    service_id: int,
    service_key: str = Form(...), name: str = Form(...),
    description: str = Form(...), price: str = Form(...),
    db: Session = Depends(get_db),
):
    create_or_update_service(db, service_key, name, description, price)
    logger.info("admin_service_updated", service_key=service_key)
    return RedirectResponse("/admin/services", status_code=303)


@router.post("/services/{service_id}/delete")
def service_delete(service_id: int, db: Session = Depends(get_db)):
    delete_service(db, service_id)
    logger.info("admin_service_deleted", service_id=service_id)
    return RedirectResponse("/admin/services", status_code=303)


# ─── FAQs ─────────────────────────────────────────────────────────────────────

@router.get("/faqs", response_class=HTMLResponse)
def faqs_list(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("faqs.html", {
        "request": request, "active": "faqs", "faqs": get_all_faqs(db),
    })


@router.get("/faqs/new", response_class=HTMLResponse)
def faq_new(request: Request):
    return templates.TemplateResponse("faq_form.html", {
        "request": request, "active": "faqs", "faq": None,
    })


@router.get("/faqs/{faq_id}/edit", response_class=HTMLResponse)
def faq_edit(request: Request, faq_id: int, db: Session = Depends(get_db)):
    faq = get_faq_by_id(db, faq_id)
    return templates.TemplateResponse("faq_form.html", {
        "request": request, "active": "faqs", "faq": faq,
    })


@router.post("/faqs/create")
def faq_create(
    question: str = Form(...), answer: str = Form(...),
    db: Session = Depends(get_db),
):
    create_or_update_faq(db, question, answer)
    logger.info("admin_faq_created", question=question[:50])
    return RedirectResponse("/admin/faqs", status_code=303)


@router.post("/faqs/update/{faq_id}")
def faq_update(
    faq_id: int, question: str = Form(...), answer: str = Form(...),
    db: Session = Depends(get_db),
):
    create_or_update_faq(db, question, answer)
    logger.info("admin_faq_updated", faq_id=faq_id)
    return RedirectResponse("/admin/faqs", status_code=303)


@router.post("/faqs/{faq_id}/delete")
def faq_delete(faq_id: int, db: Session = Depends(get_db)):
    delete_faq(db, faq_id)
    logger.info("admin_faq_deleted", faq_id=faq_id)
    return RedirectResponse("/admin/faqs", status_code=303)


# ─── Reports ──────────────────────────────────────────────────────────────────

@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, db: Session = Depends(get_db)):
    report = generate_daily_summary(db)
    return templates.TemplateResponse("reports.html", {
        "request": request, "active": "reports", "report": report,
    })
