"""
Appointment cancellation service.

Marks the appointment as ``canceled`` in the database and deletes the
corresponding Google Calendar event (if one exists).
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.crud import (
    find_appointment_for_lookup,
    update_appointment,
    create_call_event,
)
from app.models.appointment import AppointmentStatus
from app.services.integrations.google_calendar import (
    delete_calendar_event,
)

logger = get_logger(__name__)


@dataclass
class CancellationResult:
    """Result of a cancellation attempt."""

    success: bool
    appointment_id: Optional[str] = None
    message: str = ""


class CancellationService:
    """Cancel an existing appointment and remove its calendar event."""

    def cancel(
        self,
        db: Session,
        appointment_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        scheduled_date: Optional[datetime] = None,
        reason: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> CancellationResult:
        """
        Cancel an appointment.

        Lookup priority:
          1. ``appointment_id``
          2. ``customer_name`` + ``scheduled_date``

        Steps:
          1. Find the appointment.
          2. Update status → ``canceled`` in DB.
          3. Delete Google Calendar event (if ``google_event_id`` exists).
          4. Log a call event for audit.

        Returns:
            CancellationResult
        """
        # ---- locate appointment ----
        appointment = find_appointment_for_lookup(
            db,
            appointment_id=appointment_id,
            customer_name=customer_name,
            scheduled_date=scheduled_date,
        )

        if not appointment:
            # Check if an appointment exists but is already cancelled
            if appointment_id:
                from app.db.crud import get_appointment_by_id
                maybe = get_appointment_by_id(db, appointment_id)
                if maybe:
                    st = (
                        maybe.status.value
                        if hasattr(maybe.status, "value")
                        else maybe.status
                    )
                    if st == "canceled":
                        return CancellationResult(
                            success=False,
                            appointment_id=maybe.id,
                            message=(
                                "This appointment has already "
                                "been cancelled."
                            ),
                        )

            logger.warning(
                "cancel_appointment_not_found",
                appointment_id=appointment_id,
                customer_name=customer_name,
            )
            return CancellationResult(
                success=False,
                message=(
                    "Appointment not found. "
                    "Please confirm your name and appointment time."
                ),
            )

        # ---- mark as cancelled in DB ----
        update_appointment(
            db,
            appointment_id=appointment.id,
            status=AppointmentStatus.CANCELED.value,
            notes=(
                f"{appointment.notes or ''}\n"
                f"Cancelled: {reason or 'No reason provided'}"
            ).strip(),
        )

        # ---- delete Google Calendar event ----
        gcal_deleted = False
        if getattr(appointment, "google_event_id", None):
            gcal_deleted = delete_calendar_event(appointment.google_event_id)

        # ---- audit event ----
        if call_id:
            try:
                create_call_event(
                    db,
                    call_id=call_id,
                    event_type="appointment_cancelled",
                    event_data={
                        "appointment_id": appointment.id,
                        "reason": reason,
                        "gcal_deleted": gcal_deleted,
                    },
                )
            except Exception:
                pass

        scheduled_str = ""
        if appointment.scheduled_time_start:
            scheduled_str = appointment.scheduled_time_start.strftime(
                "%A %B %d at %I:%M %p"
            )

        logger.info(
            "appointment_cancelled",
            appointment_id=appointment.id,
            gcal_deleted=gcal_deleted,
        )

        return CancellationResult(
            success=True,
            appointment_id=appointment.id,
            message=(
                f"Your appointment{' for ' + scheduled_str if scheduled_str else ''} "
                "has been cancelled."
            ),
        )
