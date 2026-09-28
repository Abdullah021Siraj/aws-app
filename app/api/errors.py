"""JSON error handling and the :class:`ApiError` exception."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from ..extensions import db

logger = logging.getLogger("app.errors")

UI_PREFIX = "/ui"


def _wants_html() -> bool:
    """HTML pages render an error page; everything else gets JSON."""
    return request.path == "/" or request.path.startswith(UI_PREFIX)


class ApiError(Exception):
    """Domain error carrying an HTTP status and a machine readable code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "bad_request",
        details: Iterable[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = list(details) if details else None

    def to_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        if exc.status_code >= 500:
            logger.error(
                "api_error", extra={"status": exc.status_code, "code": exc.code}
            )
        else:
            logger.info(
                "api_error", extra={"status": exc.status_code, "code": exc.code}
            )
        return jsonify(exc.to_payload()), exc.status_code

    @app.errorhandler(HTTPException)
    def _handle_http_exception(exc: HTTPException):
        """Convert 404/405/415/... into JSON, or an HTML page under /ui."""
        code = (exc.name or "error").lower().replace(" ", "_")
        status = exc.code or 500
        if status >= 500:
            logger.error("http_error", extra={"status": status, "code": code})
        else:
            logger.info("http_error", extra={"status": status, "code": code})

        if _wants_html():
            return (
                render_template("error.html", code=code, message=exc.description, status=status),
                status,
            )

        payload = {"error": {"code": code, "message": exc.description}}
        response = jsonify(payload)
        response.status_code = status
        # Preserve headers such as ``Allow`` on a 405.
        if exc.get_headers():
            for key, value in exc.get_headers():
                if key.lower() != "content-type":
                    response.headers[key] = value
        return response

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        db.session.rollback()
        logger.exception("unhandled_exception")
        if _wants_html():
            return (
                render_template(
                    "error.html",
                    code="internal_server_error",
                    message="An unexpected error occurred.",
                    status=500,
                ),
                500,
            )
        return (
            jsonify(
                {
                    "error": {
                        "code": "internal_server_error",
                        "message": "An unexpected error occurred.",
                    }
                }
            ),
            500,
        )
