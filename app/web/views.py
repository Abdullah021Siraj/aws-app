"""HTML views: dashboard, user list and the create form."""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import func, select

from ..api.health import check_database, uptime_seconds
from ..extensions import db
from ..models import User
from ..validation import validate_user_payload
from .forms import CSRF_FIELD_NAME, csrf_protect, generate_csrf_token, set_flash

logger = logging.getLogger("app.web")

ui_bp = Blueprint("ui", __name__)

PAGE_SIZES = (10, 25, 50, 100)


@ui_bp.app_context_processor
def _inject_globals() -> dict[str, object]:
    return {
        "csrf_token": generate_csrf_token,
        "service_name": current_app.config["SERVICE_NAME"],
        "service_version": current_app.config["APP_VERSION"],
    }


@ui_bp.get("/")
def root():
    return redirect(url_for("ui.dashboard"), code=302)


@ui_bp.get("/ui")
@ui_bp.get("/ui/")
def dashboard():
    """Service overview: health, totals and the most recent users."""
    db_status, db_latency, db_error = check_database()
    total_users = 0
    recent_users: list[User] = []
    if db_status == "ok":
        try:
            total_users = db.session.scalar(select(func.count()).select_from(User)) or 0
            recent_users = list(
                db.session.execute(
                    select(User).order_by(User.id.desc()).limit(5)
                ).scalars()
            )
        except Exception:  # pragma: no cover - rendered as an unhealthy panel
            db.session.rollback()
            db_status, db_error = "error", "QueryFailed"
            db_latency = 0.0

    return render_template(
        "index.html",
        health={
            "status": db_status,
            "latency_ms": db_latency,
            "error": db_error,
            "uptime_seconds": uptime_seconds(),
        },
        total_users=total_users,
        recent_users=recent_users,
    )


@ui_bp.route("/ui/users", methods=["GET", "POST"])
def users():
    """List users with pagination, and handle the create form post."""
    if request.method == "POST":
        return _create_user()

    default_limit = current_app.config["DEFAULT_PAGE_SIZE"]
    limit, offset, errors = _pagination(default_limit)
    if errors:
        return (
            render_template(
                "users.html",
                users=[],
                pagination=_pagination_meta(0, limit, offset),
                errors=errors,
                limit=default_limit,
                page_sizes=PAGE_SIZES,
            ),
            400,
        )

    total = db.session.scalar(select(func.count()).select_from(User)) or 0
    rows = list(
        db.session.execute(
            select(User).order_by(User.id.asc()).limit(limit).offset(offset)
        ).scalars()
    )

    return render_template(
        "users.html",
        users=rows,
        pagination=_pagination_meta(total, limit, offset, len(rows)),
        errors=[],
        limit=limit,
        page_sizes=PAGE_SIZES,
    )


@ui_bp.get("/ui/users/new")
def new_user():
    return render_template("user_form.html", errors=[], form={})


def _create_user():
    csrf_protect()
    # The CSRF field travels alongside the data; the validator only sees the
    # real payload fields.
    submitted = {k: v for k, v in request.form.items() if k != CSRF_FIELD_NAME}
    data, errors = validate_user_payload(submitted)
    if errors:
        logger.info("ui_create_user_validation_failed")
        return (
            render_template(
                "user_form.html",
                errors=errors,
                form={"name": request.form.get("name", ""), "email": request.form.get("email", "")},
            ),
            400,
        )

    duplicate = db.session.execute(
        select(User.id).where(User.email == data["email"])
    ).scalar_one_or_none()
    if duplicate is not None:
        errors = [
            {
                "field": "email",
                "message": f"A user with email '{data['email']}' already exists.",
            }
        ]
        return (
            render_template(
                "user_form.html",
                errors=errors,
                form={"name": data["name"], "email": data["email"]},
            ),
            409,
        )

    user = User(name=data["name"], email=data["email"])
    db.session.add(user)
    db.session.commit()

    logger.info("ui_user_created", extra={"user_id": user.id})
    set_flash(f"Created {user.name} ({user.email}).")
    return redirect(url_for("ui.users"), code=303)


def _pagination(default_limit: int) -> tuple[int, int, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []

    def _arg(name: str, fallback: int) -> int:
        raw = request.args.get(name, "")
        if raw == "":
            return fallback
        try:
            return int(raw)
        except ValueError:
            errors.append({"field": name, "message": f"'{name}' must be a number."})
            return fallback

    limit = _arg("limit", default_limit)
    offset = _arg("offset", 0)
    if limit < 1 or limit > max(current_app.config["MAX_PAGE_SIZE"], 1):
        errors.append({"field": "limit", "message": "'limit' is out of range."})
    if offset < 0:
        errors.append({"field": "offset", "message": "'offset' must be zero or greater."})
    if errors:
        return default_limit, 0, errors
    return limit, offset, []


def _pagination_meta(total: int, limit: int, offset: int, count: int = 0) -> dict:
    has_prev = offset > 0
    has_next = offset + count < total
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "count": count,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_offset": max(offset - limit, 0),
        "next_offset": offset + limit,
    }
