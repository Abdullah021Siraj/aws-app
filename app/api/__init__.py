"""HTTP layer: blueprints, error handlers and cross cutting request hooks."""

from __future__ import annotations

import logging
import time
import uuid

from flask import Flask, g, request

from ..extensions import db
from .errors import register_error_handlers
from .health import health_bp
from .users import users_bp

logger = logging.getLogger("app.http")

REQUEST_ID_HEADER = "X-Request-ID"


def register_request_hooks(app: Flask) -> None:
    @app.before_request
    def _start_timer() -> None:
        # Honour an inbound correlation id so traces survive across services.
        g.request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        g.started_at = time.perf_counter()

    @app.after_request
    def _log_request(response):
        started_at = getattr(g, "started_at", None)
        duration_ms = (
            round((time.perf_counter() - started_at) * 1000, 3) if started_at else None
        )
        response.headers[REQUEST_ID_HEADER] = g.get("request_id", "-")
        response.headers["X-Service-Name"] = app.config["SERVICE_NAME"]
        logger.info(
            "request",
            extra={
                "request_id": g.get("request_id"),
                "method": request.method,
                "path": request.path,
                "route": request.url_rule.rule if request.url_rule else None,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.remote_addr,
            },
        )
        return response

    @app.teardown_request
    def _close_session(_exc: BaseException | None) -> None:
        # Returns the pooled connection and rolls back any open transaction.
        db.session.remove()


def register_blueprints(app: Flask) -> None:
    """Wire the HTTP surface of the service onto the app."""
    app.register_blueprint(health_bp)
    app.register_blueprint(users_bp)
    register_error_handlers(app)
    register_request_hooks(app)
