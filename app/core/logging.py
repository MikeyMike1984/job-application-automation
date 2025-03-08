# app/core/logging.py
import logging
import os
import sys
from datetime import datetime
from app.config import settings

def setup_logging():
    """Set up application logging."""
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOGGING.LEVEL))
    
    # Create formatter
    formatter = logging.Formatter(settings.LOGGING.FORMAT)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Create file handler if file path is specified
    if settings.LOGGING.FILE_PATH:
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(settings.LOGGING.FILE_PATH)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create file handler
        file_handler = logging.FileHandler(settings.LOGGING.FILE_PATH)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Create application logger
    logger = logging.getLogger(settings.APP_NAME)
    logger.info(f"Logging initialized for {settings.APP_NAME} - {settings.ENVIRONMENT} environment")
    
    return logger

# Initialize logger
logger = setup_logging()