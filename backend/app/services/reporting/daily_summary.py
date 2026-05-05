"""
Daily summary report generator.
Aggregates calls, appointments, cancellations, and reschedules for a given day.
"""
from datetime import datetime, date, timedelta, timezone
from collections import Counter
from typing import Dict, Any, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.call import Call
from app.models.appointment import Appointment, AppointmentStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


def generate_daily_summary(
    db: Session,
    target_date: date | None = None,
) -> Dict[str, Any]:
    """
    Generate a daily summary report.

    Args:
        db: Database session.
        target_date: Date to report on (defaults to today).

    Returns:
        dict with keys: date, total_calls, new_bookings, cancellations,
        reschedules, status_breakdown, top_services.
    """
    if target_date is None:
        target_date = date.today()

    day_start = datetime(
        target_date.year, target_date.month, target_date.day,
        0, 0, 0, tzinfo=timezone.utc,
    )
    day_end = day_start + timedelta(days=1)

    # ── Calls ────────────────────────────────────────────────────────────
    total_calls = (
        db.query(func.count(Call.id))
        .filter(Call.created_at >= day_start, Call.created_at < day_end)
        .scalar()
    ) or 0

    # ── Appointments created today ───────────────────────────────────────
    appts_today: List[Appointment] = (
        db.query(Appointment)
        .filter(Appointment.created_at >= day_start, Appointment.created_at < day_end)
        .all()
    )

    new_bookings = sum(
        1 for a in appts_today
        if _status_val(a) in ("pending", "confirmed", "scheduled")
    )
    cancellations = sum(1 for a in appts_today if _status_val(a) == "canceled")

    # Reschedules: updated_at != created_at AND status is scheduled
    reschedules = sum(
        1 for a in appts_today
        if _status_val(a) == "scheduled" and a.updated_at and a.created_at
        and abs((a.updated_at - a.created_at).total_seconds()) > 2
    )

    # ── Status breakdown (all-time) ──────────────────────────────────────
    all_appts: List[Appointment] = db.query(Appointment).all()
    status_counter: Counter = Counter()
    service_counter: Counter = Counter()

    for a in all_appts:
        status_counter[_status_val(a)] += 1
        if a.service_type:
            service_counter[a.service_type] += 1

    top_services: List[Tuple[str, int]] = service_counter.most_common(5)

    summary = {
        "date": target_date.isoformat(),
        "total_calls": total_calls,
        "new_bookings": new_bookings,
        "cancellations": cancellations,
        "reschedules": reschedules,
        "status_breakdown": dict(status_counter),
        "top_services": top_services,
    }

    logger.info("daily_summary_generated", **summary)
    return summary


def _status_val(appt: Appointment) -> str:
    """Return the string value of an appointment status."""
    s = appt.status
    return s.value if hasattr(s, "value") else str(s)
