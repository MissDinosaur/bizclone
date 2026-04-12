"""Knowledge Base Management API - Returns JSON for KB operations"""

import logging
from typing import Optional
from fastapi import APIRouter, Form
from pydantic import BaseModel
from knowledge_base.learning.feedback_entry import FeedbackEntry
from knowledge_base.learning.learning_mode import LearningMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb", tags=["kb"])
learning_system = LearningMode()


class KBFieldsResponse(BaseModel):
    """Response with KB field information"""
    fields: dict
    message: str


class KBSubmitRequest(BaseModel):
    """Request to submit KB update or insert"""
    kb_field: str
    operation: str  # "update" or "insert"
    customer_question: Optional[str] = None
    owner_correction: Optional[str] = None
    service_name: Optional[str] = None
    service_description: Optional[str] = None
    service_price: Optional[str] = None
    policy_name: Optional[str] = None


class KBSubmitResponse(BaseModel):
    """Response from KB submit"""
    status: str
    message: str
    result: dict = None


@router.get("/manage", response_model=KBFieldsResponse)
def get_kb_fields():
    """
    Get available KB fields for management UI.
    
    Returns:
        Dictionary mapping field names to display names
    """
    try:
        kb_fields_tuple = FeedbackEntry.get_kb_fields()
        # Convert tuple of field names to dictionary for Pydantic validation
        kb_fields_dict = {
            field: field.capitalize() for field in kb_fields_tuple
        }
        return KBFieldsResponse(
            fields=kb_fields_dict,
            message="KB fields retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting KB fields: {e}")
        return KBFieldsResponse(
            fields={},
            message=f"Error: {str(e)}"
        )


@router.post("/submit", response_model=KBSubmitResponse)
def submit_kb_update(request: KBSubmitRequest):
    """
    Submit KB update or insert operation.
    
    Args:
        request: KB update details (UPDATE/INSERT operation with specific fields)
        
    Returns:
        Result of KB operation
    """
    try:
        logger.info(f"KB API: Received request: {request.model_dump()}")
        logger.info(f"KB API: operation={request.operation}, kb_field={request.kb_field}")
        
        # Create feedback entry
        kb_entry = FeedbackEntry(
            customer_question=request.customer_question,
            owner_correction=request.owner_correction,
            policy_name=request.policy_name,
            service_name=request.service_name,
            service_description=request.service_description,
            service_price=request.service_price,
            kb_field=request.kb_field,
            operation=request.operation
        )
        
        # Process feedback through learning system
        result = learning_system.process_feedback(kb_entry.model_dump())
        
        logger.info(f"KB update processed: {result}")
        
        return KBSubmitResponse(
            status="success",
            message="KB updated successfully",
            result=result
        )
    except Exception as e:
        logger.error(f"Error submitting KB update: {e}", exc_info=True)
        return KBSubmitResponse(
            status="error",
            message=str(e),
            result=None
        )
