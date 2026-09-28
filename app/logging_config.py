"""JSON logging so container logs stay machine readable."""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from typing import Any

# Attributes added by ``logger.info(..., extra={...})`` that are promoted to
# top level JSON fields.
_EXTRA_FIELDS = (
    "request_id",
    "method",
    "path",
    "route",
    "status",
    "duration_ms",
    "client_ip",
    "user_agent",
    "user_id",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": getattr(record, "service", "users-service"),
            "message": record.getMessage(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO", service: str = "users-service") -> None:
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    logging.captureWarnings(True)
    # Uvicorn/gunicorn access logs duplicate our request logger; keep them quiet.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    for noisy in ("gunicorn.access", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(level)
    logging.getLogger("app").addFilter(_ServiceFilter(service))


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = self.service
        return True
