"""
Structured logging configuration.

Uses structlog for JSON-formatted logs in production
or colored console output in development.
"""

import logging
import sys
from typing import Optional

import structlog

from kalshi_bot.config import settings


def setup_logging(
    level: Optional[str] = None,
    format: Optional[str] = None,
) -> None:
    """
    Configure structured logging.
    
    Args:
        level: Log level (default from settings)
        format: Output format: 'json' or 'console' (default from settings)
    """
    level = level or settings.log_level
    fmt = format or settings.log_format
    
    # Shared processors
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    if fmt == "json":
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )
    
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
