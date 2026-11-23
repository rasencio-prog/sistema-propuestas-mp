"""Logging estructurado en JSON (structlog) con request_id y filtro de secretos."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars

_SECRET_KEY_PATTERN = re.compile(
    r"(ticket|password|contrase|secret|api_key|apikey|token|authorization|encryption_key)",
    re.IGNORECASE,
)
_MASK = "***"


def _scrub_secrets(_logger: Any, _method_name: str, event_dict: Mapping[str, Any]) -> dict[str, Any]:
    """Enmascara valores de campos cuyo nombre sugiere un secreto (CLAUDE.md: nunca loguear secretos)."""
    scrubbed: dict[str, Any] = {}
    for key, value in event_dict.items():
        if _SECRET_KEY_PATTERN.search(key):
            scrubbed[key] = _MASK
        else:
            scrubbed[key] = value
    return scrubbed


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(level=log_level, format="%(message)s")

    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _scrub_secrets,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(log_level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(*args: Any, **kwargs: Any) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(*args, **kwargs)


def bind_request_context(**kwargs: Any) -> None:
    bind_contextvars(**kwargs)


def clear_request_context() -> None:
    clear_contextvars()
