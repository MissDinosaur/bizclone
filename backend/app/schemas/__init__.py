"""
Pydantic schemas for API requests and responses.
"""
from app.schemas.health import HealthCheck, ServiceStatus
from app.schemas.calendar import (
    AppointmentBase,
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    CalendarDayView,
    CalendarWeekView,
    CalendarMonthView,
    AvailableSlot,
    AvailabilityResponse,
    CancelRequest,
    RescheduleRequest,
    CancelRescheduleResponse,
)

__all__ = [
    "HealthCheck",
    "ServiceStatus",
    "AppointmentBase",
    "AppointmentCreate",
    "AppointmentUpdate",
    "AppointmentResponse",
    "CalendarDayView",
    "CalendarWeekView",
    "CalendarMonthView",
    "AvailableSlot",
    "AvailabilityResponse",
    "CancelRequest",
    "RescheduleRequest",
    "CancelRescheduleResponse",
]
