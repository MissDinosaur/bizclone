"""
Google Calendar integration.

Creates calendar events when appointments are successfully scheduled.
Uses service account credentials from GOOGLE_CREDENTIALS_FILE or
GOOGLE_APPLICATION_CREDENTIALS. If not set, event creation is skipped.

Provides conflict detection and next-available-slot logic so that
events never overlap on the target calendar.
"""
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Any, List, Dict

from app.config.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Lazy-loaded singleton objects
_creds: Optional[Any] = None
_service: Optional[Any] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_credentials():
    """Load service-account credentials from file if configured."""
    global _creds
    if _creds is not None:
        return _creds

    import os

    # Step 1: get path from settings or env
    path = getattr(settings, "google_credentials_file", None) or ""
    if not path:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

    if not path:
        # fallback to project-root safe path
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        path = os.path.join(BASE_DIR, "credentials", "google_calendar.json")

    # Step 2: check file exists (VERY IMPORTANT DEBUG STEP)
    if not os.path.exists(path):
        logger.warning(
            "google_calendar_credentials_missing",
            path=path,
        )
        return None

    try:
        from google.oauth2 import service_account

        _creds = service_account.Credentials.from_service_account_file(
            path,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        return _creds

    except Exception as e:
        logger.warning(
            "google_calendar_credentials_failed",
            path=path,
            error=str(e),
        )
        return None


def _build_service():
    """Return a reusable Google Calendar API service instance."""
    global _service
    if _service is not None:
        return _service

    creds = _get_credentials()
    if not creds:
        return None

    try:
        from googleapiclient.discovery import build
        _service = build("calendar", "v3", credentials=creds)
        return _service
    except ImportError:
        logger.warning(
            "google_calendar_skipped",
            reason="google-api-python-client not installed",
        )
        return None
    except Exception as e:
        logger.warning("google_calendar_service_build_failed", error=str(e))
        return None


def _to_rfc3339(dt: datetime) -> str:
    """Convert a datetime to an RFC-3339 string suitable for the API."""
    s = dt.isoformat()
    if dt.tzinfo is None:
        s += "Z"
    return s


def _get_target_calendar_id() -> str:
    """Return the calendar ID from ``GOOGLE_TARGET_CALENDAR`` env var.

    Falls back to the ``google_target_calendar`` setting, then ``"primary"``.
    """
    import os
    cal_id = os.environ.get("GOOGLE_TARGET_CALENDAR", "")
    if cal_id:
        return cal_id
    return getattr(settings, "google_target_calendar", "primary") or "primary"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_events(
    time_min: datetime,
    time_max: datetime,
    calendar_id: Optional[str] = None,
) -> List[Dict]:
    """
    Return existing events in *[time_min, time_max)* from Google Calendar.

    Each element is a raw event dict as returned by the Calendar API.
    Returns an empty list when credentials are missing or an error occurs.
    """
    if calendar_id is None:
        calendar_id = _get_target_calendar_id()

    service = _build_service()
    if not service:
        return []

    try:
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=_to_rfc3339(time_min),
                timeMax=_to_rfc3339(time_max),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])
    except Exception as e:
        logger.warning(
            "google_calendar_list_events_failed",
            calendar_id=calendar_id,
            time_min=time_min.isoformat(),
            time_max=time_max.isoformat(),
            error=str(e),
        )
        return []


def has_conflict(
    start_time: datetime,
    duration_minutes: int = 60,
    calendar_id: Optional[str] = None,
) -> bool:
    """
    Check whether *start_time* … *start_time + duration* overlaps any
    existing event on the Google Calendar.
    """
    if calendar_id is None:
        calendar_id = _get_target_calendar_id()
    end_time = start_time + timedelta(minutes=duration_minutes)
    events = list_events(start_time, end_time, calendar_id)
    return len(events) > 0


def find_next_available_slot(
    preferred_start: datetime,
    duration_minutes: int = 60,
    calendar_id: Optional[str] = None,
    search_days: int = 14,
) -> Optional[datetime]:
    """
    Starting from *preferred_start*, find the first slot of
    *duration_minutes* that does **not** conflict with an existing
    Google Calendar event and falls within configured business hours.

    Business-hours configuration is read from ``settings``:
      - ``business_hours_start`` (e.g. ``"09:00"``)
      - ``business_hours_end``   (e.g. ``"18:00"``)
      - ``max_daily_appointments``
      - ``appointment_duration_minutes``

    Returns ``None`` if no slot is found within *search_days*.
    """
    if calendar_id is None:
        calendar_id = _get_target_calendar_id()

    bh_start = _parse_time(settings.business_hours_start)
    bh_end = _parse_time(settings.business_hours_end)
    slot_delta = timedelta(minutes=duration_minutes)
    buffer_minutes = getattr(
        settings, "appointment_buffer_minutes", 15
    )
    step = timedelta(minutes=duration_minutes + buffer_minutes)
    max_daily = getattr(settings, "max_daily_appointments", 8)

    cursor = preferred_start
    end_boundary = preferred_start + timedelta(days=search_days)

    while cursor < end_boundary:
        # Skip weekends
        if cursor.weekday() >= 5:
            cursor = _next_business_morning(cursor, bh_start)
            continue

        slot_end_time = (cursor + slot_delta).time()

        # Before business hours → jump to opening
        if cursor.time() < bh_start:
            cursor = cursor.replace(
                hour=bh_start.hour,
                minute=bh_start.minute,
                second=0,
                microsecond=0,
            )
            continue

        # Past business hours → next day
        if cursor.time() >= bh_end or slot_end_time > bh_end:
            cursor = _next_business_morning(cursor, bh_start)
            continue

        # Check daily cap on this calendar day
        day_start = cursor.replace(
            hour=bh_start.hour,
            minute=bh_start.minute,
            second=0,
            microsecond=0,
        )
        day_end = cursor.replace(
            hour=bh_end.hour,
            minute=bh_end.minute,
            second=0,
            microsecond=0,
        )
        day_events = list_events(day_start, day_end, calendar_id)
        if len(day_events) >= max_daily:
            cursor = _next_business_morning(cursor, bh_start)
            continue

        # Check for conflict at this exact slot
        if not has_conflict(cursor, duration_minutes, calendar_id):
            logger.info(
                "google_calendar_slot_found",
                calendar_id=calendar_id,
                slot_start=cursor.isoformat(),
                slot_end=(cursor + slot_delta).isoformat(),
            )
            return cursor

        # Advance by one step
        cursor += step

    logger.warning(
        "google_calendar_no_slot_found",
        calendar_id=calendar_id,
        preferred_start=preferred_start.isoformat(),
        search_days=search_days,
    )
    return None


def create_calendar_event(
    summary: str,
    start_time: datetime,
    duration_minutes: int = 60,
    calendar_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Optional[str]:
    """
    Create a Google Calendar event.

    Args:
        summary: Event title (e.g. "Leak Repair – Michael Weber").
        start_time: datetime (timezone-aware or naive; stored as-is).
        duration_minutes: Event length in minutes.
        calendar_id: Target calendar (defaults to GOOGLE_TARGET_CALENDAR).
        description: Optional event description.

    Returns:
        Event ID if created, ``None`` if skipped or failed.
    """
    if calendar_id is None:
        calendar_id = _get_target_calendar_id()

    service = _build_service()
    if not service:
        logger.debug(
            "google_calendar_skipped",
            reason="no_credentials_or_service",
        )
        return None

    try:
        end_time = start_time + timedelta(minutes=duration_minutes)
        start_str = _to_rfc3339(start_time)
        end_str = _to_rfc3339(end_time)

        event = {
            "summary": summary,
            "description": description or "",
            "start": {"dateTime": start_str},
            "end": {"dateTime": end_str},
        }

        created = (
            service.events()
            .insert(calendarId=calendar_id, body=event)
            .execute()
        )
        event_id = created.get("id")
        logger.info(
            "google_calendar_event_created",
            event_id=event_id,
            calendar_id=calendar_id,
            summary=summary,
            start=start_str,
            end=end_str,
        )
        return event_id
    except Exception as e:
        logger.warning(
            "google_calendar_event_failed",
            calendar_id=calendar_id,
            summary=summary,
            error=str(e),
        )
        return None


def delete_calendar_event(
    event_id: str,
    calendar_id: Optional[str] = None,
) -> bool:
    """
    Delete a Google Calendar event by its event ID.

    Returns ``True`` if deleted successfully, ``False`` otherwise.
    """
    if calendar_id is None:
        calendar_id = _get_target_calendar_id()

    service = _build_service()
    if not service:
        logger.debug(
            "google_calendar_delete_skipped",
            reason="no_credentials_or_service",
        )
        return False

    try:
        service.events().delete(
            calendarId=calendar_id, eventId=event_id
        ).execute()
        logger.info(
            "google_calendar_event_deleted",
            event_id=event_id,
            calendar_id=calendar_id,
        )
        return True
    except Exception as e:
        logger.warning(
            "google_calendar_event_delete_failed",
            event_id=event_id,
            calendar_id=calendar_id,
            error=str(e),
        )
        return False


def update_calendar_event(
    event_id: str,
    summary: Optional[str] = None,
    start_time: Optional[datetime] = None,
    duration_minutes: int = 60,
    description: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> bool:
    """
    Update an existing Google Calendar event.

    Only the fields provided (non-``None``) are changed.
    Returns ``True`` on success, ``False`` on failure.
    """
    if calendar_id is None:
        calendar_id = _get_target_calendar_id()

    service = _build_service()
    if not service:
        logger.debug(
            "google_calendar_update_skipped",
            reason="no_credentials_or_service",
        )
        return False

    try:
        # Fetch existing event
        existing = (
            service.events()
            .get(calendarId=calendar_id, eventId=event_id)
            .execute()
        )

        if summary is not None:
            existing["summary"] = summary
        if description is not None:
            existing["description"] = description
        if start_time is not None:
            end_time = start_time + timedelta(minutes=duration_minutes)
            existing["start"] = {"dateTime": _to_rfc3339(start_time)}
            existing["end"] = {"dateTime": _to_rfc3339(end_time)}

        service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=existing,
        ).execute()

        logger.info(
            "google_calendar_event_updated",
            event_id=event_id,
            calendar_id=calendar_id,
        )
        return True
    except Exception as e:
        logger.warning(
            "google_calendar_event_update_failed",
            event_id=event_id,
            calendar_id=calendar_id,
            error=str(e),
        )
        return False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_time(time_str: str) -> dt_time:
    """Parse ``"HH:MM"`` → ``datetime.time``."""
    hour, minute = map(int, time_str.split(":"))
    return dt_time(hour=hour, minute=minute)


def _next_business_morning(dt: datetime, bh_start: dt_time) -> datetime:
    """Advance *dt* to the next weekday at *bh_start*."""
    next_day = dt + timedelta(days=1)
    next_day = next_day.replace(
        hour=bh_start.hour, minute=bh_start.minute, second=0, microsecond=0
    )
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day
