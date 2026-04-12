"""Calendar Data API - Returns JSON for booking calendar operations"""

import logging
import calendar
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
import os

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from database.orm_models import Booking
import config.config as cfg

logger = logging.getLogger(__name__)

# Setup database
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url, echo=False)
SessionLocal = sessionmaker(bind=engine)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class BookingItemResponse(BaseModel):
    """Single booking item"""
    booking_id: str
    customer_email: str
    customer_name: str
    time: str
    status: str


class CalendarDayResponse(BaseModel):
    """Single day in calendar"""
    day: int
    date: Optional[str] = None
    bookings: List[BookingItemResponse] = []


class CalendarDataResponse(BaseModel):
    """Complete calendar data for a month"""
    year: int
    month: int
    month_name: str
    calendar_days: List[CalendarDayResponse]
    prev_month: int
    prev_year: int
    next_month: int
    next_year: int
    total_bookings: int
    total_customers: int
    message: str = "Calendar data retrieved successfully"


@router.get("/data", response_model=CalendarDataResponse)
def get_calendar_data(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get calendar data for a specific month.
    
    Args:
        month: Month (1-12), defaults to current month
        year: Year, defaults to current year
        
    Returns:
        Calendar grid with bookings data
    """
    try:
        # Get current date
        now = datetime.now()
        
        # Use provided month/year or default to current
        if month is None or year is None:
            month = now.month
            year = now.year
        else:
            # Validate month/year
            if month < 1 or month > 12:
                month = now.month
            if year < 1900 or year > 2100:
                year = now.year
        
        # Get first and last day of month
        first_day_of_month = datetime(year, month, 1)
        if month == 12:
            last_day_of_month = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day_of_month = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Query bookings for current month
        bookings = db.query(Booking).filter(
            and_(
                Booking.slot >= first_day_of_month,
                Booking.slot <= last_day_of_month.replace(hour=23, minute=59, second=59),
                Booking.status == "confirmed"
            )
        ).order_by(Booking.slot).all()
        
        # Organize bookings by date
        bookings_by_date = {}
        for booking in bookings:
            date_key = booking.slot.strftime("%Y-%m-%d")
            if date_key not in bookings_by_date:
                bookings_by_date[date_key] = []
            bookings_by_date[date_key].append(booking)
        
        # Generate calendar grid with data
        cal = calendar.monthcalendar(year, month)
        calendar_days = []
        
        for week in cal:
            for day in week:
                if day == 0:
                    calendar_days.append(CalendarDayResponse(day=0))
                else:
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    day_bookings = []
                    
                    if date_str in bookings_by_date:
                        for booking in bookings_by_date[date_str]:
                            booking_item = BookingItemResponse(
                                booking_id=str(booking.id),
                                customer_email=booking.customer_email,
                                customer_name=booking.customer_email.split('@')[0],
                                time=booking.slot.strftime("%H:%M"),
                                status=booking.status
                            )
                            day_bookings.append(booking_item)
                    
                    calendar_days.append(CalendarDayResponse(
                        day=day,
                        date=date_str,
                        bookings=day_bookings
                    ))
        
        # Month navigation
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        
        # Month names
        month_names = ["", "January", "February", "March", "April", "May", "June",
                       "July", "August", "September", "October", "November", "December"]
        month_name = month_names[month]
        
        # Statistics
        total_customers = len(set(b.customer_email for b in bookings))
        
        return CalendarDataResponse(
            year=year,
            month=month,
            month_name=month_name,
            calendar_days=calendar_days,
            prev_month=prev_month,
            prev_year=prev_year,
            next_month=next_month,
            next_year=next_year,
            total_bookings=len(bookings),
            total_customers=total_customers,
            message="Calendar data retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting calendar data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/booking/{booking_id}")
def get_booking_detail(
    booking_id: str,  # Changed from int to str - Booking.id is String(50)
    db: Session = Depends(get_db)
):
    """
    Get details for a specific booking.
    
    Args:
        booking_id: Booking ID
        
    Returns:
        Booking details
    """
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {booking_id} not found"
            )
        
        # Extract customer name from email
        customer_name = booking.customer_email.split('@')[0] if booking.customer_email else "Unknown"
        
        return {
            "id": booking.id,
            "customer_email": booking.customer_email,
            "customer_name": customer_name,
            "slot": booking.slot.isoformat(),
            "time": booking.slot.strftime("%H:%M"),  # Extract time part
            "date": booking.slot.strftime("%Y-%m-%d"),  # Extract date part
            "status": booking.status,
            "notes": booking.notes,
            "channel": booking.channel,
            "booked_at": booking.booked_at.isoformat() if booking.booked_at else None,
            "created_at": booking.created_at.isoformat() if booking.created_at else None,
            "message": "Booking detail retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting booking detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
