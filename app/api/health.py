"""Liveness / readiness endpoint."""

from __future__ import annotations

import logging
import time

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db

logger = logging.getLogger("app.health")

health_bp = Blueprint("health", __name__)


def _start_time() -> float:
    return current_app.extensions.get("service_start_monotonic", time.monotonic())


def uptime_seconds() -> float:
    """Seconds since the process started serving."""
    return round(time.monotonic() - _start_time(), 3)


def check_database() -> tuple[str, float, str | None]:
    """Cheap round trip to Postgres. Returns ``(status, latency_ms, error)``."""
    started = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        return "ok", round((time.perf_counter() - started) * 1000, 3), None
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.warning("health_database_check_failed", extra={"error": type(exc).__name__})
        return "error", round((time.perf_counter() - started) * 1000, 3), type(exc).__name__
    finally:
        # Never hold a connection open after a health probe.
        db.session.remove()


@health_bp.get("/health")
def health():
    """Readiness probe: 200 when the service can serve traffic, else 503."""
    db_status, db_latency, db_error = check_database()
    healthy = db_status == "ok"

    database_check: dict[str, object] = {"status": db_status, "latency_ms": db_latency}
    if db_error:
        database_check["error"] = db_error

    payload = {
        "status": "ok" if healthy else "degraded",
        "service": current_app.config["SERVICE_NAME"],
        "version": current_app.config["APP_VERSION"],
        "api_version": current_app.config["API_VERSION"],
        "uptime_seconds": uptime_seconds(),
        "checks": {"database": database_check},
    }
    return jsonify(payload), 200 if healthy else 503
