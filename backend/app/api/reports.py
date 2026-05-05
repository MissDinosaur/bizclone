"""
Reporting API — JSON endpoints for daily summary reports.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.reporting.daily_summary import generate_daily_summary

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/daily")
def daily_report(
    target_date: Optional[date] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    db: Session = Depends(get_db),
):
    """Get daily summary report as JSON."""
    return generate_daily_summary(db, target_date)
