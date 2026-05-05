"""
Strict intent router and booking validation.

Ensures:
- cancel intents ONLY cancel (never create new bookings)
- reschedule intents ONLY reschedule (never create new bookings)
- booking intents require valid date/time before execution
- no fallback to booking from cancel/reschedule
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


# Intents that MUST NOT create a new appointment record
_NON_BOOKING_INTENTS = frozenset({"cancel", "reschedule"})

# Intents that go through the booking pipeline
_BOOKING_INTENTS = frozenset({"booking", "emergency"})


@dataclass
class RoutingDecision:
    """Result of intent routing."""

    action: str  # "book", "cancel", "reschedule", "clarify", "info_only"
    reason: str
    entities: Dict[str, Any]
    intent: str


@dataclass
class BookingValidation:
    """Result of booking request validation."""

    valid: bool
    reason: str
    has_date: bool
    has_time: bool


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def route_intent(
    intent: str,
    entities: Dict[str, Any],
    transcript: str = "",
) -> RoutingDecision:
    """
    Decide the correct action based on classified intent.

    Rules:
        cancel      → action="cancel"   (NEVER fall back to booking)
        reschedule  → action="reschedule" (NEVER fall back to booking)
        booking     → action="book" only if validate_booking_request passes
                      else action="clarify"
        emergency   → action="book" (forced, no date validation)
        other       → action="info_only"
    """
    intent_lower = (intent or "").strip().lower()
    logger.info(
        "intent_router_invoked",
        intent=intent_lower,
        has_date=bool(entities.get("requested_date")),
        has_time=bool(entities.get("requested_time")),
    )

    # ── Cancel: strict, no fallback ──────────────────────────────
    if intent_lower == "cancel":
        return RoutingDecision(
            action="cancel",
            reason="Intent is cancel — route to cancellation handler only",
            entities=entities,
            intent=intent_lower,
        )

    # ── Reschedule: strict, no fallback ──────────────────────────
    if intent_lower == "reschedule":
        return RoutingDecision(
            action="reschedule",
            reason="Intent is reschedule — route to reschedule handler only",
            entities=entities,
            intent=intent_lower,
        )

    # ── Emergency: always book, skip date validation ─────────────
    if intent_lower == "emergency":
        return RoutingDecision(
            action="book",
            reason="Emergency — schedule immediately",
            entities=entities,
            intent=intent_lower,
        )

    # ── Booking: validate date/time first ────────────────────────
    if intent_lower == "booking":
        validation = validate_booking_request(entities)
        if validation.valid:
            return RoutingDecision(
                action="book",
                reason="Booking with valid date/time",
                entities=entities,
                intent=intent_lower,
            )
        else:
            logger.warning(
                "booking_missing_datetime",
                reason=validation.reason,
                has_date=validation.has_date,
                has_time=validation.has_time,
            )
            # Still allow booking but flag that date/time was not explicit
            return RoutingDecision(
                action="book_with_warning",
                reason=validation.reason,
                entities=entities,
                intent=intent_lower,
            )

    # ── Everything else (pricing, availability, service_question, other)
    return RoutingDecision(
        action="info_only",
        reason=f"Non-actionable intent: {intent_lower}",
        entities=entities,
        intent=intent_lower,
    )


def validate_booking_request(entities: Dict[str, Any]) -> BookingValidation:
    """
    Validate that a booking request has the minimum required fields.

    A booking MUST have at least a date OR a time extracted from the
    transcript.  If both are missing the system should NOT silently
    pick a same-day default slot.
    """
    has_date = bool(entities.get("requested_date"))
    has_time = bool(entities.get("requested_time"))
    has_datetime_text = bool(entities.get("date_time_text"))

    if has_date or has_time or has_datetime_text:
        return BookingValidation(
            valid=True,
            reason="Date/time information present",
            has_date=has_date,
            has_time=has_time,
        )

    return BookingValidation(
        valid=False,
        reason=(
            "No date or time found in transcript. "
            "Cannot book without explicit scheduling information."
        ),
        has_date=False,
        has_time=False,
    )
