"""User collection endpoints: ``GET /users`` and ``POST /users``."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ..extensions import db
from ..models import User
from ..validation import validate_user_payload
from .errors import ApiError

logger = logging.getLogger("app.users")

users_bp = Blueprint("users", __name__)


def _pagination() -> tuple[int, int]:
    default_limit = current_app.config["DEFAULT_PAGE_SIZE"]
    max_limit = current_app.config["MAX_PAGE_SIZE"]
    errors: list[dict[str, str]] = []

    def _int_arg(name: str, fallback: int) -> int:
        raw = request.args.get(name)
        if raw is None or raw == "":
            return fallback
        try:
            return int(raw)
        except ValueError:
            errors.append({"field": name, "message": f"'{name}' must be an integer."})
            return fallback

    limit = _int_arg("limit", default_limit)
    offset = _int_arg("offset", 0)

    if limit < 1:
        errors.append({"field": "limit", "message": "'limit' must be greater than 0."})
    elif limit > max_limit:
        errors.append(
            {"field": "limit", "message": f"'limit' must be at most {max_limit}."}
        )
    if offset < 0:
        errors.append({"field": "offset", "message": "'offset' must be zero or greater."})

    if errors:
        raise ApiError(
            "Invalid query parameters.",
            code="validation_error",
            details=errors,
        )
    return limit, offset


@users_bp.get("/users")
def list_users():
    """List users ordered by id, newest last, with offset pagination."""
    limit, offset = _pagination()

    try:
        total = db.session.scalar(select(func.count()).select_from(User)) or 0
        users = (
            db.session.execute(
                select(User).order_by(User.id.asc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error("list_users_failed", extra={"error": type(exc).__name__})
        raise ApiError(
            "Could not retrieve users.", status_code=503, code="database_unavailable"
        ) from exc

    return (
        jsonify(
            {
                "data": [user.to_dict() for user in users],
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "count": len(users),
                    "has_more": offset + len(users) < total,
                },
            }
        ),
        200,
    )


@users_bp.post("/users")
def create_user():
    """Create a user. Returns 201 with the created resource."""
    # get_json() raises 415 when the content type is wrong and 400 when the
    # body is not valid JSON; both are converted by the error handlers.
    payload = request.get_json()
    data, errors = validate_user_payload(payload)
    if errors:
        raise ApiError(
            "Request validation failed.",
            code="validation_error",
            details=errors,
        )

    existing = db.session.execute(
        select(User.id).where(User.email == data["email"])
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError(
            f"A user with email '{data['email']}' already exists.",
            status_code=409,
            code="duplicate_email",
        )

    user = User(name=data["name"], email=data["email"])
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError as exc:
        # Lost the race against a concurrent insert with the same email.
        db.session.rollback()
        raise ApiError(
            f"A user with email '{data['email']}' already exists.",
            status_code=409,
            code="duplicate_email",
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error("create_user_failed", extra={"error": type(exc).__name__})
        raise ApiError(
            "Could not create the user.", status_code=503, code="database_unavailable"
        ) from exc

    logger.info("user_created", extra={"user_id": user.id})
    return jsonify({"data": user.to_dict()}), 201
