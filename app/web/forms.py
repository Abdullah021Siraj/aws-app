"""Form helpers for the HTML pages: CSRF tokens and flash messages."""

from __future__ import annotations

import secrets

from flask import abort, flash, request, session

CSRF_SESSION_KEY = "csrf_token"
CSRF_FIELD_NAME = "csrf_token"


def generate_csrf_token() -> str:
    """Return the per-session CSRF token, creating it on first use."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def csrf_protect() -> None:
    """Validate the submitted token on every unsafe HTTP method."""
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    expected = session.get(CSRF_SESSION_KEY)
    submitted = request.form.get(CSRF_FIELD_NAME, "")
    if not expected or not secrets.compare_digest(expected, submitted):
        abort(400, description="Invalid or missing CSRF token. Reload the page.")


def set_flash(message: str, category: str = "success") -> None:
    flash(message, category)


def pop_flashes() -> list[dict[str, str]]:
    """Drain the flash queue so messages are shown exactly once."""
    messages = [
        {"category": category, "message": message}
        for category, message in session.pop("_flashes", [])
    ]
    return messages
