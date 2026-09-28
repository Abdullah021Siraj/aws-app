"""End to end tests against a real PostgreSQL instance.

Skipped unless ``TEST_DATABASE_URL`` is exported, e.g.::

    docker compose up -d db
    TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/users_db_test \\
        pytest tests/test_integration.py
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import delete

from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

# Mark every test in this module so ``pytest -m "not integration"`` skips it.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not configured"
    ),
]


@pytest.fixture(scope="module")
def pg_app():
    class PgTestingConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL

    application = create_app(PgTestingConfig)
    with application.app_context():
        db.drop_all()
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def pg_client(pg_app):
    with pg_app.app_context():
        # Each test starts from an empty table.
        db.session.execute(delete(User))
        db.session.commit()
    return pg_app.test_client()


def test_round_trip_against_postgres(pg_client):
    assert pg_client.get("/health").get_json()["status"] == "ok"

    created = pg_client.post(
        "/users", json={"name": "Grace Hopper", "email": "grace@example.com"}
    )
    assert created.status_code == 201

    users = pg_client.get("/users").get_json()
    assert users["pagination"]["total"] == 1
    assert users["data"][0]["email"] == "grace@example.com"
    assert users["data"][0]["created_at"].endswith("+00:00")


def test_unique_constraint_is_enforced_by_postgres(pg_client):
    body = {"name": "Alan Turing", "email": "alan@example.com"}
    assert pg_client.post("/users", json=body).status_code == 201
    assert pg_client.post("/users", json=body).status_code == 409
