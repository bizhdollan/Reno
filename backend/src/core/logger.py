"""
Centralized Logging Configuration for RenovationTech Backend

Features:
- Rotating file handler (10MB max, 5 backups)
- Human-readable format with timestamps
- Module-aware logging
- Exception logging with full tracebacks
- File-only output (no console)

Usage:
    from src.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Processing started")
    logger.error("Something failed", exc_info=True)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# Log directory and file configuration
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5
LOG_LEVEL = logging.INFO

# Human-readable log format
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Track if logging has been configured
_logging_configured = False


def setup_logging(
    log_level: int = LOG_LEVEL,
    log_file: Optional[Path] = None,
    max_bytes: int = MAX_BYTES,
    backup_count: int = BACKUP_COUNT,
) -> None:
    """
    Configure the root logger with rotating file handler.

    Should be called once at application startup (in main.py).
    Subsequent calls are ignored to prevent duplicate handlers.

    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: logs/app.log)
        max_bytes: Max file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    global _logging_configured

    if _logging_configured:
        return

    # Use default log file if not specified
    if log_file is None:
        log_file = LOG_FILE

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Create rotating file handler
    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _logging_configured = True

    # Log that logging is configured
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Logging initialized")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    logger.info(f"Max file size: {max_bytes / (1024*1024):.1f}MB, Backups: {backup_count}")
    logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance

    Usage:
        logger = get_logger(__name__)
        logger.info("Starting process")
        logger.debug("Debug info: %s", data)
        logger.warning("Warning message")
        logger.error("Error occurred", exc_info=True)
    """
    return logging.getLogger(name)


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance
        message: Context message
        exc: Exception to log

    Usage:
        try:
            risky_operation()
        except Exception as e:
            log_exception(logger, "Failed to process data", e)
    """
    logger.error(f"{message}: {type(exc).__name__}: {exc}", exc_info=True)


def log_step(logger: logging.Logger, step: str, details: Optional[str] = None) -> None:
    """
    Log a processing step for flow debugging.

    Args:
        logger: Logger instance
        step: Step name/description
        details: Optional additional details

    Usage:
        log_step(logger, "PROJECT_BASICS", "Collecting project title")
        log_step(logger, "IMAGE_ANALYSIS", f"Analyzing {len(images)} images")
    """
    if details:
        logger.info(f"[STEP] {step} - {details}")
    else:
        logger.info(f"[STEP] {step}")


def log_flow_start(logger: logging.Logger, flow_name: str, context: dict) -> None:
    """
    Log the start of a major flow/process.

    Args:
        logger: Logger instance
        flow_name: Name of the flow
        context: Relevant context data
    """
    logger.info(f">>> FLOW START: {flow_name}")
    for key, value in context.items():
        # Truncate long values
        str_value = str(value)
        if len(str_value) > 100:
            str_value = str_value[:100] + "..."
        logger.info(f"    {key}: {str_value}")


def log_flow_end(logger: logging.Logger, flow_name: str, result: str = "SUCCESS") -> None:
    """
    Log the end of a major flow/process.

    Args:
        logger: Logger instance
        flow_name: Name of the flow
        result: Result status
    """
    logger.info(f"<<< FLOW END: {flow_name} - {result}")
