"""
Appointment rescheduling service.

Validates the new slot, updates the DB, and patches the Google Calendar
event — all without touching the original booking pipeline.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.logging import get_logger
from app.db.crud import (
    find_appointment_for_lookup,
    update_appointment,
    create_call_event,
)
from app.models.appointment import AppointmentStatus
from app.services.integrations.google_calendar import (
    has_conflict,
    find_next_available_slot,
    update_calendar_event,
)
from app.services.scheduling.scheduler import SchedulingService

logger = get_logger(__name__)


@dataclass
class RescheduleResult:
    """Result of a reschedule attempt."""

    success: bool
    appointment_id: Optional[str] = None
    new_start: Optional[datetime] = None
    new_end: Optional[datetime] = None
    message: str = ""


class RescheduleService:
    """Reschedule an existing appointment to a new time slot."""

    def __init__(self):
        self._scheduler = SchedulingService()

    def reschedule(
        self,
        db: Session,
        new_start_time: datetime,
        appointment_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        scheduled_date: Optional[datetime] = None,
        new_end_time: Optional[datetime] = None,
        reason: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> RescheduleResult:
        """
        Reschedule an appointment.

        Steps:
          1. Look up the appointment.
          2. Validate the new slot (business hours, conflicts).
          3. Update DB times.
          4. Update Google Calendar event.
          5. Audit-log the action.
        """
        # ---- locate appointment ----
        appointment = find_appointment_for_lookup(
            db,
            appointment_id=appointment_id,
            customer_name=customer_name,
            scheduled_date=scheduled_date,
        )

        if not appointment:
            logger.warning(
                "reschedule_appointment_not_found",
                appointment_id=appointment_id,
                customer_name=customer_name,
            )
            return RescheduleResult(
                success=False,
                message=(
                    "Appointment not found. "
                    "Please confirm your name and appointment time."
                ),
            )

        # ---- already cancelled? ----
        status_val = (
            appointment.status.value
            if hasattr(appointment.status, "value")
            else appointment.status
        )
        if status_val == "canceled":
            return RescheduleResult(
                success=False,
                appointment_id=appointment.id,
                message="Cannot reschedule a cancelled appointment.",
            )

        # ---- resolve duration ----
        duration = getattr(settings, "appointment_duration_minutes", 60)
        if new_end_time is None:
            new_end_time = new_start_time + timedelta(minutes=duration)

        # ---- check DB-level availability ----
        slot = self._scheduler.check_availability(
            db, new_start_time,
            new_end_time - new_start_time,
        )
        if not slot.is_available:
            # Try Google Calendar auto-find
            alt = find_next_available_slot(
                preferred_start=new_start_time,
                duration_minutes=duration,
            )
            if alt is not None:
                new_start_time = alt
                new_end_time = alt + timedelta(minutes=duration)
            else:
                return RescheduleResult(
                    success=False,
                    appointment_id=appointment.id,
                    message=(
                        f"Requested time is not available: {slot.reason}. "
                        "No alternative slot found within the next 14 days."
                    ),
                )

        # ---- Google Calendar conflict check ----
        if has_conflict(new_start_time, duration):
            alt = find_next_available_slot(
                preferred_start=new_start_time,
                duration_minutes=duration,
            )
            if alt is not None:
                new_start_time = alt
                new_end_time = alt + timedelta(minutes=duration)
            else:
                return RescheduleResult(
                    success=False,
                    appointment_id=appointment.id,
                    message="Calendar conflict and no alternative slot found.",
                )

        # ---- update DB ----
        old_start = appointment.scheduled_time_start
        update_appointment(
            db,
            appointment_id=appointment.id,
            scheduled_time_start=new_start_time,
            scheduled_time_end=new_end_time,
            scheduled_date=new_start_time,
            status=AppointmentStatus.SCHEDULED.value,
            notes=(
                f"{appointment.notes or ''}\n"
                f"Rescheduled from {old_start}: {reason or 'No reason'}"
            ).strip(),
        )

        # ---- update Google Calendar event ----
        gcal_updated = False
        if getattr(appointment, "google_event_id", None):
            gcal_updated = update_calendar_event(
                event_id=appointment.google_event_id,
                start_time=new_start_time,
                duration_minutes=duration,
            )

        # ---- audit event ----
        if call_id:
            try:
                create_call_event(
                    db,
                    call_id=call_id,
                    event_type="appointment_rescheduled",
                    event_data={
                        "appointment_id": appointment.id,
                        "old_start": (
                            old_start.isoformat() if old_start else None
                        ),
                        "new_start": new_start_time.isoformat(),
                        "new_end": new_end_time.isoformat(),
                        "reason": reason,
                        "gcal_updated": gcal_updated,
                    },
                )
            except Exception:
                pass

        new_str = new_start_time.strftime("%A %B %d at %I:%M %p")

        logger.info(
            "appointment_rescheduled",
            appointment_id=appointment.id,
            new_start=new_start_time.isoformat(),
            gcal_updated=gcal_updated,
        )

        return RescheduleResult(
            success=True,
            appointment_id=appointment.id,
            new_start=new_start_time,
            new_end=new_end_time,
            message=f"Your appointment has been moved to {new_str}.",
        )
