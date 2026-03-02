"""
Logging Configuration Module

Centralized logging setup for the entire application.
Supports console and file logging with appropriate formatting.
"""
import logging
import logging.handlers
import os
from config.config import LOG_LEVEL, ENVIRONMENT

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)


def setup_logging():
    """
    Configure logging for the entire application.
    
    - Console output: Shows INFO level and above
    - File output: Rotates daily, keeps 7 days of logs
    - Format: [TIMESTAMP] [LEVEL] [MODULE]: MESSAGE
    - Third-party libraries: Suppressed at WARNING level (only serious issues shown)
    """
    
    # Get root logger
    logger = logging.getLogger()
    
    # Set root level based on environment
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # Console Handler (always INFO level for production, DEBUG for development)
    console_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    
    # File Handler (DEBUG level - keeps all logs)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, "bizclone.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=7,  # Keep 7 days of logs
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Error File Handler (ERROR level only)
    error_file_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, "bizclone_errors.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=7,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    
    # Formatter
    detailed_formatter = logging.Formatter(
        fmt='[%(asctime)s] [%(levelname)-8s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        fmt='[%(levelname)-8s] [%(name)s] %(message)s'
    )
    
    # Apply formatters
    console_handler.setFormatter(simple_formatter)
    file_handler.setFormatter(detailed_formatter)
    error_file_handler.setFormatter(detailed_formatter)
    
    # Add handlers to root logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_file_handler)
    

    # Suppress DEBUG logs from noisy third-party libraries
    # Only show WARNING and above from these libraries
    third_party_loggers = [
        'googleapiclient.discovery',      # Google API client
        'urllib3.connectionpool',         # HTTP connection pool
        'httpcore.http11',               # HTTP core
        'httpx',                         # HTTP client
        'httpcore',                      # HTTP core library
        'openai._base_client',           # OpenAI client
        'openai',                        # OpenAI library
        'chromadb',                      # ChromaDB
        'transformers',                  # Hugging Face transformers
        'sentence_transformers',         # Sentence transformers
        'asyncio',                       # Async IO
        'python_multipart.multipart',    # Multipart form data parsing
    ]
    
    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Log startup info
    logger.info(f"Logging initialized | Environment: {ENVIRONMENT} | Level: {LOG_LEVEL}")
    logger.info("Third-party library debug logs suppressed (WARNING level only)")


# Call setup on module import
setup_logging()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Usage:
        from logger_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)

