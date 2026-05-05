"""
Structured logging configuration using structlog.
Provides JSON-formatted logs for production and human-readable logs for development.
"""
import logging
import sys
from typing import Any, Dict
import structlog
from structlog.types import EventDict, Processor

from app.config.settings import settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log entries."""
    event_dict["app"] = settings.app_name
    event_dict["version"] = settings.app_version
    event_dict["environment"] = settings.environment
    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application."""
    
    # Determine if we should use JSON formatting
    use_json = settings.environment in ["production", "staging"]
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )
    
    # Processors for structlog
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
    ]
    
    if use_json:
        # Production: JSON formatting
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ])
    else:
        # Development: Human-readable formatting
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True)
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Convenience function for logging call events
def log_call_event(
    logger: structlog.stdlib.BoundLogger,
    event_type: str,
    call_sid: str,
    **kwargs: Any
) -> None:
    """
    Log a call-related event with standard fields.
    
    Args:
        logger: Logger instance
        event_type: Type of event (e.g., "call_started", "transcription_complete")
        call_sid: Call session ID
        **kwargs: Additional fields to log
    """
    logger.info(
        event_type,
        call_sid=call_sid,
        event_type=event_type,
        **kwargs
    )


# Convenience function for logging errors
def log_error(
    logger: structlog.stdlib.BoundLogger,
    error: Exception,
    context: Dict[str, Any] | None = None,
    **kwargs: Any
) -> None:
    """
    Log an error with context.
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Additional context dictionary
        **kwargs: Additional fields to log
    """
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {}),
        **kwargs
    }
    logger.error("error_occurred", **error_data, exc_info=True)


# Initialize logging on module import
configure_logging()

