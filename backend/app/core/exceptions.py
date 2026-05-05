"""
Custom exceptions for the BizClone application.
"""
from typing import Any, Dict, Optional


class BizCloneException(Exception):
    """Base exception for all BizClone errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ConfigurationError(BizCloneException):
    """Raised when there's a configuration error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class DatabaseError(BizCloneException):
    """Raised when there's a database error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class RecordingDownloadError(BizCloneException):
    """Raised when there's an error downloading a recording."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class TranscriptionError(BizCloneException):
    """Raised when there's an error during transcription."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class AIServiceError(BizCloneException):
    """Raised when there's an error with AI services (OpenAI, etc.)."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class TTSError(BizCloneException):
    """Raised when there's an error with Text-to-Speech."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class SchedulingError(BizCloneException):
    """Raised when there's an error with scheduling."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class ValidationError(BizCloneException):
    """Raised when there's a validation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=422, details=details)


class NotFoundError(BizCloneException):
    """Raised when a resource is not found."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)


class RateLimitError(BizCloneException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=429, details=details)

