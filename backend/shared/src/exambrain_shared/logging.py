"""Structured JSON logging via structlog.

Configures structlog for JSON output with the level taken from the
``LOG_LEVEL`` environment variable (default ``INFO``), and routes stdlib
logging (e.g. uvicorn) through the same processors.
"""

import logging
import sys

import structlog


def configure_logging(level: str | None = None) -> None:
    """Configure structlog + stdlib logging for JSON output.

    Args:
        level: Log level name; falls back to the ``LOG_LEVEL`` env var via
            :class:`~exambrain_shared.config.Settings`, defaulting to INFO.
    """
    if level is None:
        from exambrain_shared.config import get_settings

        level = get_settings().log_level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(numeric_level)

    # Let uvicorn loggers propagate to the JSON root handler.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
