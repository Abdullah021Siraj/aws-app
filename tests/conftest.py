"""Shared pytest fixtures (fast, in-memory SQLite by default)."""

from __future__ import annotations

import pytest

from app import create_app
from app.config import TestingConfig
from app.extensions import db


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def create_user(client):
    def _create(name: str = "Ada Lovelace", email: str = "ada@example.com"):
        return client.post("/users", json={"name": name, "email": email})

    return _create
