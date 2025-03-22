"""
Logging configuration for the application.
"""
import logging
import sys
from typing import Optional

from app.config import LOG_LEVEL


def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Set up and configure a logger with the given name.

    Args:
        name: The name of the logger.
        level: The logging level. Defaults to LOG_LEVEL from config.

    Returns:
        A configured logger instance.
    """
    if level is None:
        level = LOG_LEVEL

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level))

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)

    # Add handler to the logger
    logger.addHandler(handler)

    return logger 