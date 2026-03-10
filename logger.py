"""
JSON logging utility for structured logging
"""
import json
import logging
from datetime import datetime
from typing import Optional, Any
from config import LOG_LEVEL


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "method": getattr(record, "method", ""),
            "time": datetime.utcnow().isoformat() + "Z",
            "message": record.getMessage(),
            "log_level": record.levelname,
            "data": getattr(record, "data", "")
        }
        return json.dumps(log_data)


def setup_logger(name: str = "app", level: str = "INFO") -> logging.Logger:
    """
    Setup and return a JSON logger
    
    Parameters:
    - name: Logger name
    - level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger = logging.getLogger(name)
    
    # Map string level to logging constant
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    log_level = level_map.get(level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create console handler with JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger


def log_json(
    logger: logging.Logger,
    level: str,
    message: str,
    method: str = "",
    data: Any = ""
):
    """Helper function to log with custom fields"""
    extra = {
        "method": method,
        "data": data if data else ""
    }
    
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra=extra)


logger = setup_logger(level=LOG_LEVEL)
