"""
Pydantic schemas for calendar API endpoints.
"""
from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from datetime import date as DateType


class AppointmentBase(BaseModel):
    """Base appointment schema."""
    
    service_type: Optional[str] = Field(None, description="Type of service")
    service_description: Optional[str] = Field(None, description="Service description")
    address: Optional[str] = Field(None, description="Service address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State")
    zip_code: Optional[str] = Field(None, description="ZIP code")
    contact_name: Optional[str] = Field(None, description="Contact name")
    contact_phone: Optional[str] = Field(None, description="Contact phone")
    contact_email: Optional[str] = Field(None, description="Contact email")
    notes: Optional[str] = Field(None, description="Additional notes")


class AppointmentCreate(AppointmentBase):
    """Schema for creating an appointment."""
    
    customer_id: str = Field(..., description="Customer ID")
    scheduled_time_start: datetime = Field(..., description="Appointment start time")
    scheduled_time_end: datetime = Field(..., description="Appointment end time")
    urgency: str = Field(default="medium", description="Urgency level")


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""
    
    scheduled_time_start: Optional[datetime] = Field(None, description="New start time")
    scheduled_time_end: Optional[datetime] = Field(None, description="New end time")
    status: Optional[str] = Field(None, description="Appointment status")
    service_type: Optional[str] = Field(None, description="Service type")
    service_description: Optional[str] = Field(None, description="Service description")
    address: Optional[str] = Field(None, description="Service address")
    notes: Optional[str] = Field(None, description="Notes")


class AppointmentResponse(AppointmentBase):
    """Schema for appointment response."""
    
    id: str = Field(..., description="Appointment ID")
    customer_id: str = Field(..., description="Customer ID")
    call_id: str = Field(..., description="Call ID")
    status: str = Field(..., description="Appointment status")
    urgency: str = Field(..., description="Urgency level")
    scheduled_time_start: Optional[datetime] = Field(None, description="Scheduled start time")
    scheduled_time_end: Optional[datetime] = Field(None, description="Scheduled end time")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config:
        from_attributes = True


class CalendarDayView(BaseModel):
    """Schema for a single day's calendar view."""

    date: DateType = Field(..., description="Date")
    appointments: List[AppointmentResponse] = Field(default_factory=list, description="Appointments for this day")
    total_appointments: int = Field(..., description="Total number of appointments")
    available_slots: int = Field(..., description="Number of available slots")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2026-03-03",
                "appointments": [],
                "total_appointments": 3,
                "available_slots": 5
            }
        }


class CalendarWeekView(BaseModel):
    """Schema for a week's calendar view."""

    start_date: DateType = Field(..., description="Week start date")
    end_date: DateType = Field(..., description="Week end date")
    days: List[CalendarDayView] = Field(..., description="Days in the week")
    total_appointments: int = Field(..., description="Total appointments in the week")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2026-03-03",
                "end_date": "2026-03-09",
                "days": [],
                "total_appointments": 15
            }
        }


class CalendarMonthView(BaseModel):
    """Schema for a month's calendar view."""
    
    year: int = Field(..., description="Year")
    month: int = Field(..., description="Month (1-12)")
    days: List[CalendarDayView] = Field(..., description="Days in the month")
    total_appointments: int = Field(..., description="Total appointments in the month")
    
    class Config:
        json_schema_extra = {
            "example": {
                "year": 2026,
                "month": 3,
                "days": [],
                "total_appointments": 45
            }
        }


class AvailableSlot(BaseModel):
    """Schema for an available time slot."""
    
    start_time: datetime = Field(..., description="Slot start time")
    end_time: datetime = Field(..., description="Slot end time")
    is_available: bool = Field(..., description="Whether the slot is available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_time": "2026-03-03T10:00:00",
                "end_time": "2026-03-03T11:00:00",
                "is_available": True
            }
        }


class AvailabilityResponse(BaseModel):
    """Schema for availability check response."""

    date: DateType = Field(..., description="Date checked")
    available_slots: List[AvailableSlot] = Field(..., description="Available time slots")
    total_slots: int = Field(..., description="Total slots in the day")
    available_count: int = Field(..., description="Number of available slots")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2026-03-03",
                "available_slots": [],
                "total_slots": 8,
                "available_count": 5
            }
        }


# -----------------------------------------------------------------------
# Cancel / Reschedule Schemas
# -----------------------------------------------------------------------

class CancelRequest(BaseModel):
    """Request body for cancelling an appointment."""

    appointment_id: Optional[str] = Field(
        None, description="Appointment ID (preferred lookup key)"
    )
    customer_name: Optional[str] = Field(
        None, description="Customer name for fuzzy lookup"
    )
    appointment_date: Optional[datetime] = Field(
        None, description="Scheduled date for fuzzy lookup"
    )
    reason: Optional[str] = Field(
        None, description="Cancellation reason"
    )


class RescheduleRequest(BaseModel):
    """Request body for rescheduling an appointment."""

    appointment_id: Optional[str] = Field(
        None, description="Appointment ID (preferred lookup key)"
    )
    customer_name: Optional[str] = Field(
        None, description="Customer name for fuzzy lookup"
    )
    appointment_date: Optional[datetime] = Field(
        None, description="Original scheduled date for lookup"
    )
    new_start_time: datetime = Field(
        ..., description="Desired new start time"
    )
    new_end_time: Optional[datetime] = Field(
        None,
        description="Desired new end time (defaults to start + duration)",
    )
    reason: Optional[str] = Field(
        None, description="Reschedule reason"
    )


class CancelRescheduleResponse(BaseModel):
    """Shared response for cancel / reschedule endpoints."""

    success: bool = Field(..., description="Whether the action succeeded")
    appointment_id: Optional[str] = Field(
        None, description="Appointment ID"
    )
    message: str = Field(..., description="Human-readable result message")
    action: str = Field(
        ..., description="Action performed: cancel | reschedule"
    )
    new_start_time: Optional[datetime] = Field(
        None, description="New start time (reschedule only)"
    )
    new_end_time: Optional[datetime] = Field(
        None, description="New end time (reschedule only)"
    )

