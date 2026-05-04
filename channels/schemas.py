"""
Standardized Response Schemas (Pydantic Models) for All Channels
Response Schemas for Channel Agent Responses

Defines standardized Pydantic models that ALL channels must follow.
This ensures consistent API contracts across email, teams, whatsapp, call, and facebook.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class IntentType(str, Enum):
    """Standardized intent classification across all channels."""
    PRICING_INQUIRY = "pricing_inquiry"
    APPOINTMENT = "appointment_booking_request"
    CANCELLATION = "cancellation_request"
    WORKING_HOURS = "business_hours_question"
    EMERGENCY = "emergency_service_request"
    FAQ = "general_faq_question"


class BookingResponseSchema(BaseModel):
    """Standardized booking response returned by all channels."""
    
    id: str = Field(..., description="Unique booking ID")
    slot: str = Field(..., description="Booked slot in format YYYY-MM-DD HH:MM")
    customer_email: str = Field(..., description="Customer email address")
    channel: str = Field(..., description="Channel through which booking was made")
    status: str = Field(..., description="Booking status: confirmed or failed")
    booked_at: str = Field(..., description="Timestamp when booking was created")
    notes: Optional[str] = Field(None, description="Additional booking notes")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "id": "BK20260302100000001",
                "slot": "2026-03-05 10:00",
                "customer_email": "customer@example.com",
                "channel": "email",
                "status": "confirmed",
                "booked_at": "2026-03-02T10:30:00",
                "notes": "Customer requested morning slot"
            }
        }


class ChannelMessageResponseSchema(BaseModel):
    """
    Unified response format for ANY channel message processing.
    
    ALL channels (email, teams, whatsapp, call, facebook) MUST return this schema.
    This enables consistent frontend handling and testing.
    """
    
    channel: str = Field(..., description="Channel name: email, teams, whatsapp, call, facebook")
    status: str = Field(
        ..., 
        description="Processing status: auto_send=ready to send, needs_review=owner must review, failed=error occurred"
    )
    intent: IntentType = Field(..., description="Classified customer intent")
    reply: str = Field(..., description="Generated reply text")
    booking: Optional[BookingResponseSchema] = Field(None, description="Booking details if appointment was booked")
    retrieved_docs: Optional[List[str]] = Field(None, description="KB documents used to generate reply")
    error_code: Optional[str] = Field(None, description="Error code if status is failed")
    error_message: Optional[str] = Field(None, description="Detailed error message if status is failed")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "channel": "email",
                "status": "auto_send",
                "intent": "appointment_booking_request",
                "reply": "Hello! I've booked your appointment for March 5 at 10:00 AM. Looking forward to helping you!",
                "booking": {
                    "id": "BK20260302100000001",
                    "slot": "2026-03-05 10:00",
                    "customer_email": "customer@example.com",
                    "channel": "email",
                    "status": "confirmed",
                    "booked_at": "2026-03-02T10:30:00",
                    "notes": None
                },
                "retrieved_docs": ["Service_Appointment_Procedure", "Emergency_Charges"],
                "error_code": None,
                "error_message": None
            }
        }


class ErrorResponseSchema(BaseModel):
    """Standard error response for all channels."""
    
    channel: str = Field(..., description="Channel name")
    status: str = Field(default="failed", description="Always 'failed' for error responses")
    intent: Optional[IntentType] = Field(None, description="Intent if it could be determined before error")
    reply: Optional[str] = Field(None, description="Partial reply if one was generated")
    error_code: str = Field(..., description="Error code for programmatic handling")
    error_message: str = Field(..., description="Human-readable error message")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "channel": "teams",
                "status": "failed",
                "intent": None,
                "reply": None,
                "error_code": "MESSAGE_PARSE_ERROR",
                "error_message": "Unable to parse incoming Teams message"
            }
        }


# Enums for standardizing across channels
class MessageStatus(str, Enum):
    """Status values for channel message processing."""
    AUTO_SEND = "auto_send"  # Ready to send automatically
    NEEDS_REVIEW = "needs_review"  # Requires owner review (usually for emergency cases)
    FAILED = "failed"  # Processing failed


class BookingStatus(str, Enum):
    """Status values for bookings."""
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"
