"""Request payload validation (no third party schema dependency)."""

from __future__ import annotations

import re
from typing import Any

MAX_NAME_LENGTH = 120
MAX_EMAIL_LENGTH = 255
ALLOWED_USER_FIELDS = frozenset({"name", "email"})

# Pragmatic email check: local@domain.tld with no whitespace.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def validate_user_payload(payload: Any) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Return ``(cleaned_data, errors)`` for a ``POST /users`` body."""
    errors: list[dict[str, str]] = []
    data: dict[str, str] = {}

    if not isinstance(payload, dict):
        return data, [{"field": "body", "message": "Request body must be a JSON object."}]

    unknown = sorted(set(payload) - ALLOWED_USER_FIELDS)
    if unknown:
        errors.append(
            {
                "field": "body",
                "message": f"Unknown field(s): {', '.join(unknown)}.",
            }
        )

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append({"field": "name", "message": "'name' is required and must be a string."})
    elif len(name.strip()) > MAX_NAME_LENGTH:
        errors.append(
            {"field": "name", "message": f"'name' must be at most {MAX_NAME_LENGTH} characters."}
        )
    else:
        data["name"] = name.strip()

    email = payload.get("email")
    if not isinstance(email, str) or not email.strip():
        errors.append({"field": "email", "message": "'email' is required and must be a string."})
    else:
        normalized = email.strip().lower()
        if len(normalized) > MAX_EMAIL_LENGTH:
            errors.append(
                {
                    "field": "email",
                    "message": f"'email' must be at most {MAX_EMAIL_LENGTH} characters.",
                }
            )
        elif not EMAIL_RE.match(normalized):
            errors.append({"field": "email", "message": "'email' is not a valid email address."})
        else:
            data["email"] = normalized

    return data, errors
