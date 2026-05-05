"""
Calendar API endpoints for appointment management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from app.core.logging import get_logger
from app.db import get_db
from app.db.crud import (
    get_appointment_by_id,
    create_appointment,
    update_appointment,
    get_customer_by_id
)
from app.models.appointment import AppointmentStatus
from app.schemas.calendar import (
    AppointmentResponse,
    AppointmentCreate,
    AppointmentUpdate,
    CalendarDayView,
    CalendarWeekView,
    CalendarMonthView,
    AvailabilityResponse,
    CancelRequest,
    RescheduleRequest,
    CancelRescheduleResponse,
)
from app.services.calendar import CalendarService
from app.services.scheduling import (
    SchedulingService,
    CancellationService,
    RescheduleService,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/calendar", tags=["Calendar"])

# Initialize services
calendar_service = CalendarService()
scheduler = SchedulingService()
cancellation_service = CancellationService()
reschedule_service = RescheduleService()


@router.get(
    "/day/{target_date}",
    response_model=CalendarDayView,
    summary="Get Day View",
    description="Get calendar view for a specific day"
)
async def get_day_view(
    target_date: date,
    db: Session = Depends(get_db)
):
    """
    Get calendar view for a single day.

    Args:
        target_date: Date to view (YYYY-MM-DD)
        db: Database session

    Returns:
        CalendarDayView: Day view with appointments
    """
    logger.info("calendar_day_view_requested", date=target_date.isoformat())

    day_view = calendar_service.get_day_view(db, target_date)

    return day_view


@router.get(
    "/week/{start_date}",
    response_model=CalendarWeekView,
    summary="Get Week View",
    description="Get calendar view for a week starting from the given date"
)
async def get_week_view(
    start_date: date,
    db: Session = Depends(get_db)
):
    """
    Get calendar view for a week.

    Args:
        start_date: Week start date (YYYY-MM-DD)
        db: Database session

    Returns:
        CalendarWeekView: Week view with daily breakdowns
    """
    logger.info("calendar_week_view_requested", start_date=start_date.isoformat())

    week_view = calendar_service.get_week_view(db, start_date)

    return week_view


@router.get(
    "/month/{year}/{month}",
    response_model=CalendarMonthView,
    summary="Get Month View",
    description="Get calendar view for a specific month"
)
async def get_month_view(
    year: int,
    month: int,
    db: Session = Depends(get_db)
):
    """
    Get calendar view for a month.

    Args:
        year: Year (e.g., 2026)
        month: Month (1-12)
        db: Database session

    Returns:
        CalendarMonthView: Month view with daily breakdowns
    """
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12"
        )

    logger.info("calendar_month_view_requested", year=year, month=month)

    month_view = calendar_service.get_month_view(db, year, month)

    return month_view


@router.get(
    "/availability/{target_date}",
    response_model=AvailabilityResponse,
    summary="Check Availability",
    description="Get available time slots for a specific date"
)
async def check_availability(
    target_date: date,
    num_slots: int = Query(default=8, ge=1, le=20, description="Number of slots to return"),
    db: Session = Depends(get_db)
):
    """
    Check availability for a specific date.

    Args:
        target_date: Date to check (YYYY-MM-DD)
        num_slots: Number of slots to return (1-20)
        db: Database session

    Returns:
        AvailabilityResponse: Available time slots
    """
    logger.info(
        "availability_check_requested",
        date=target_date.isoformat(),
        num_slots=num_slots
    )

    availability = calendar_service.get_availability(db, target_date, num_slots)

    return availability


@router.get(
    "/appointments/upcoming",
    response_model=List[AppointmentResponse],
    summary="Get Upcoming Appointments",
    description="Get upcoming appointments for the next N days"
)
async def get_upcoming_appointments(
    days_ahead: int = Query(default=7, ge=1, le=90, description="Days to look ahead"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum appointments to return"),
    db: Session = Depends(get_db)
):
    """
    Get upcoming appointments.

    Args:
        days_ahead: Number of days to look ahead (1-90)
        limit: Maximum number of appointments (1-200)
        db: Database session

    Returns:
        List[AppointmentResponse]: Upcoming appointments
    """
    logger.info(
        "upcoming_appointments_requested",
        days_ahead=days_ahead,
        limit=limit
    )

    appointments = calendar_service.get_upcoming_appointments(db, days_ahead, limit)

    return appointments


@router.get(
    "/appointments/status/{status}",
    response_model=List[AppointmentResponse],
    summary="Get Appointments by Status",
    description="Get appointments filtered by status"
)
async def get_appointments_by_status(
    status: str,
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    db: Session = Depends(get_db)
):
    """
    Get appointments by status.

    Args:
        status: Appointment status (pending, confirmed, scheduled, completed, canceled, no_show)
        start_date: Optional start date
        end_date: Optional end date
        db: Database session

    Returns:
        List[AppointmentResponse]: Filtered appointments
    """
    # Validate status
    try:
        status_enum = AppointmentStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join([s.value for s in AppointmentStatus])}"
        )

    logger.info(
        "appointments_by_status_requested",
        status=status,
        start_date=start_date.isoformat() if start_date else None,
        end_date=end_date.isoformat() if end_date else None
    )

    appointments = calendar_service.get_appointments_by_status(
        db, status_enum, start_date, end_date
    )

    return appointments


@router.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get Appointment",
    description="Get a specific appointment by ID"
)
async def get_appointment(
    appointment_id: str,
    db: Session = Depends(get_db)
):
    """
    Get appointment by ID.

    Args:
        appointment_id: Appointment ID
        db: Database session

    Returns:
        AppointmentResponse: Appointment details
    """
    appointment = get_appointment_by_id(db, appointment_id)

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment not found: {appointment_id}"
        )

    logger.info("appointment_retrieved", appointment_id=appointment_id)

    return appointment


@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Appointment",
    description="Create a new appointment"
)
async def create_new_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new appointment.

    Args:
        appointment_data: Appointment data
        db: Database session

    Returns:
        AppointmentResponse: Created appointment
    """
    # Validate customer exists
    customer = get_customer_by_id(db, appointment_data.customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer not found: {appointment_data.customer_id}"
        )

    # Check availability
    availability = scheduler.check_availability(
        db,
        appointment_data.scheduled_time_start,
        appointment_data.scheduled_time_end - appointment_data.scheduled_time_start
    )

    if not availability.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Time slot not available: {availability.reason}"
        )

    # Create appointment (need a dummy call_id for now)
    # In production, this would be linked to an actual call
    appointment = create_appointment(
        db,
        call_id="manual_" + str(datetime.utcnow().timestamp()),
        customer_id=appointment_data.customer_id,
        scheduled_time_start=appointment_data.scheduled_time_start,
        scheduled_time_end=appointment_data.scheduled_time_end,
        service_type=appointment_data.service_type,
        service_description=appointment_data.service_description,
        address=appointment_data.address,
        city=appointment_data.city,
        state=appointment_data.state,
        zip_code=appointment_data.zip_code,
        contact_name=appointment_data.contact_name,
        contact_phone=appointment_data.contact_phone,
        contact_email=appointment_data.contact_email,
        notes=appointment_data.notes,
        urgency=appointment_data.urgency,
        status=AppointmentStatus.SCHEDULED
    )

    logger.info(
        "appointment_created",
        appointment_id=appointment.id,
        customer_id=appointment_data.customer_id,
        scheduled_time=appointment_data.scheduled_time_start.isoformat()
    )

    return appointment


@router.patch(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Update Appointment",
    description="Update an existing appointment"
)
async def update_existing_appointment(
    appointment_id: str,
    appointment_data: AppointmentUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an appointment.

    Args:
        appointment_id: Appointment ID
        appointment_data: Updated appointment data
        db: Database session

    Returns:
        AppointmentResponse: Updated appointment
    """
    # Check appointment exists
    existing = get_appointment_by_id(db, appointment_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Appointment not found: {appointment_id}"
        )

    # If updating time, check availability
    if appointment_data.scheduled_time_start and appointment_data.scheduled_time_end:
        duration = appointment_data.scheduled_time_end - appointment_data.scheduled_time_start
        availability = scheduler.check_availability(
            db,
            appointment_data.scheduled_time_start,
            duration
        )

        if not availability.is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Time slot not available: {availability.reason}"
            )

    # Update appointment
    update_data = appointment_data.model_dump(exclude_unset=True)
    updated = update_appointment(db, appointment_id, **update_data)

    logger.info("appointment_updated", appointment_id=appointment_id)

    return updated



# ====================================================================
# Cancel / Reschedule Endpoints
# ====================================================================


@router.post(
    "/appointments/cancel",
    response_model=CancelRescheduleResponse,
    summary="Cancel Appointment",
    description="Cancel an existing appointment by ID or customer name + date",
)
async def cancel_appointment_endpoint(
    body: CancelRequest,
    db: Session = Depends(get_db),
):
    """
    Cancel an appointment.

    Accepts either ``appointment_id`` (preferred) or
    ``customer_name`` + ``appointment_date`` for fuzzy lookup.
    """
    if not body.appointment_id and not body.customer_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide appointment_id or customer_name",
        )

    result = cancellation_service.cancel(
        db,
        appointment_id=body.appointment_id,
        customer_name=body.customer_name,
        scheduled_date=body.appointment_date,
        reason=body.reason,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.message,
        )

    return CancelRescheduleResponse(
        success=True,
        appointment_id=result.appointment_id,
        message=result.message,
        action="cancel",
    )


@router.post(
    "/appointments/reschedule",
    response_model=CancelRescheduleResponse,
    summary="Reschedule Appointment",
    description="Reschedule an existing appointment to a new time",
)
async def reschedule_appointment_endpoint(
    body: RescheduleRequest,
    db: Session = Depends(get_db),
):
    """
    Reschedule an appointment.

    Accepts ``appointment_id`` (preferred) or
    ``customer_name`` + ``appointment_date`` for lookup, plus
    ``new_start_time`` (required).
    """
    if not body.appointment_id and not body.customer_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide appointment_id or customer_name",
        )

    result = reschedule_service.reschedule(
        db,
        new_start_time=body.new_start_time,
        appointment_id=body.appointment_id,
        customer_name=body.customer_name,
        scheduled_date=body.appointment_date,
        new_end_time=body.new_end_time,
        reason=body.reason,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.message,
        )

    return CancelRescheduleResponse(
        success=True,
        appointment_id=result.appointment_id,
        message=result.message,
        action="reschedule",
        new_start_time=result.new_start,
        new_end_time=result.new_end,
    )
