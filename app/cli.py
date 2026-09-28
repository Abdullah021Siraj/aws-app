"""Operational CLI commands (``flask <command>``)."""

from __future__ import annotations

import logging

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import User

logger = logging.getLogger("app.cli")

SEED_USERS = [
    {"name": "Ada Lovelace", "email": "ada@example.com"},
    {"name": "Alan Turing", "email": "alan@example.com"},
    {"name": "Grace Hopper", "email": "grace@example.com"},
]


def register_cli(app: Flask) -> None:
    app.cli.add_command(init_db)
    app.cli.add_command(drop_db)
    app.cli.add_command(seed_db)
    app.cli.add_command(check_db)


@click.command("init-db")
@with_appcontext
def init_db() -> None:
    """Create any missing tables (idempotent)."""
    try:
        db.create_all()
    except SQLAlchemyError as exc:
        raise click.ClickException(f"Failed to create schema: {exc}") from exc
    click.echo("Database schema is up to date.")


@click.command("drop-db")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@with_appcontext
def drop_db(yes: bool) -> None:
    """Drop all tables. Destructive: development helper only."""
    if not yes:
        click.confirm("This deletes all data. Continue?", abort=True)
    db.drop_all()
    click.echo("All tables dropped.")


@click.command("seed-db")
@with_appcontext
def seed_db() -> None:
    """Insert demo users, skipping emails that already exist."""
    created = 0
    for row in SEED_USERS:
        exists = db.session.execute(
            select(User.id).where(User.email == row["email"])
        ).scalar_one_or_none()
        if exists is None:
            db.session.add(User(**row))
            created += 1
    db.session.commit()
    click.echo(f"Seeded {created} user(s); {len(SEED_USERS) - created} already existed.")


@click.command("check-db")
@with_appcontext
def check_db() -> None:
    """Print a connection check, handy for debugging deployments."""
    try:
        db.session.execute(db.text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise click.ClickException(f"Database unreachable: {exc}") from exc
    finally:
        db.session.remove()
    click.echo("Database connection OK.")
