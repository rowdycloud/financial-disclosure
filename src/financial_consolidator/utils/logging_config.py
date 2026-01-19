"""Logging configuration for the financial consolidator."""

import logging
import sys
from pathlib import Path

# Default log file name
DEFAULT_LOG_FILE = "financial_consolidator.log"

# Sensitive field names to sanitize in log output
SENSITIVE_FIELDS = {'password', 'token', 'ssn', 'account_number', 'card_number', 'pin', 'secret', 'api_key'}


def _sanitize_context(context: dict[str, object]) -> dict[str, object]:
    """Sanitize sensitive fields in context dict.

    Args:
        context: Dictionary of context values.

    Returns:
        Dictionary with sensitive fields masked.
    """
    return {k: '***' if k.lower() in SENSITIVE_FIELDS else v for k, v in context.items()}

# Log format with timestamp, level, module, and message
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    console_output: bool = True,
) -> logging.Logger:
    """Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Path to log file. If None, uses DEFAULT_LOG_FILE.
        console_output: Whether to also output to console.

    Returns:
        The root logger configured for the application.
    """
    # Get numeric log level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger("financial_consolidator")
    logger.setLevel(numeric_level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # File handler
    if log_file is None:
        log_file = DEFAULT_LOG_FILE

    log_path = Path(log_file)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (typically __name__).

    Returns:
        A logger instance for the module.
    """
    return logging.getLogger(f"financial_consolidator.{name}")


class LogContext:
    """Context manager for logging operations with file/line context."""

    def __init__(self, logger: logging.Logger, operation: str, **context: object):
        """Initialize log context.

        Args:
            logger: Logger instance to use.
            operation: Name of the operation being performed.
            **context: Additional context to include in log messages.
        """
        self.logger = logger
        self.operation = operation
        self.context = context

    def __enter__(self) -> "LogContext":
        sanitized = _sanitize_context(self.context)
        context_str = ", ".join(f"{k}={v}" for k, v in sanitized.items())
        self.logger.debug(f"Starting {self.operation}: {context_str}")
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> bool:
        if exc_type is not None:
            self.logger.error(
                f"Error in {self.operation}: {exc_type.__name__}: {exc_val}",
                exc_info=True,
            )
        else:
            self.logger.debug(f"Completed {self.operation}")
        return False  # Don't suppress exceptions
