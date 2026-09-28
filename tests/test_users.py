"""Tests for GET /users and POST /users."""

from __future__ import annotations

import pytest
from sqlalchemy import text


# --------------------------------------------------------------------------- #
# POST /users
# --------------------------------------------------------------------------- #
def test_create_user_returns_201_and_persists(client, app):
    response = client.post(
        "/users", json={"name": "Ada Lovelace", "email": "Ada@Example.com"}
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["id"] == 1
    assert data["name"] == "Ada Lovelace"
    assert data["email"] == "ada@example.com"  # normalised to lowercase
    assert data["created_at"] is not None

    from app.extensions import db
    from app.models import User

    with app.app_context():
        assert db.session.get(User, data["id"]) is not None


@pytest.mark.parametrize(
    "payload, expected_field",
    [
        ({}, "name"),
        ({"name": "Ada"}, "email"),
        ({"name": "", "email": "ada@example.com"}, "name"),
        ({"name": "Ada", "email": "not-an-email"}, "email"),
        ({"name": 42, "email": "ada@example.com"}, "name"),
        ({"name": "A" * 121, "email": "ada@example.com"}, "name"),
    ],
)
def test_create_user_rejects_invalid_payloads(client, payload, expected_field):
    response = client.post("/users", json=payload)

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "validation_error"
    assert expected_field in {detail["field"] for detail in error["details"]}


def test_create_user_rejects_unknown_fields(client):
    response = client.post(
        "/users", json={"name": "Ada", "email": "ada@example.com", "role": "admin"}
    )

    assert response.status_code == 400
    details = response.get_json()["error"]["details"]
    assert any("role" in detail["message"] for detail in details)


def test_create_user_rejects_duplicate_email(client, create_user):
    assert create_user().status_code == 201

    response = create_user(name="Impostor", email="ADA@example.com")

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "duplicate_email"


def test_duplicate_race_is_caught_by_the_unique_constraint(client, monkeypatch, app):
    """A concurrent insert that slips past the pre-check must still yield 409."""
    from sqlalchemy.orm import Session

    from app.extensions import db as database

    original_commit = Session.commit

    def commit_with_racing_insert(self):
        # A row with this email lands between the view's SELECT and the INSERT.
        with app.app_context():
            self.execute(
                text("INSERT INTO users (name, email) VALUES (:n, :e)"),
                {"n": "Racer", "e": "race@example.com"},
            )
        return original_commit(self)

    monkeypatch.setattr(Session, "commit", commit_with_racing_insert)

    response = client.post(
        "/users", json={"name": "Racer", "email": "race@example.com"}
    )

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "duplicate_email"


def test_create_user_requires_json_content_type(client):
    response = client.post("/users", data="name=Ada", content_type="text/plain")

    assert response.status_code == 415
    assert response.get_json()["error"]["code"] == "unsupported_media_type"


def test_create_user_rejects_malformed_json(client):
    response = client.post(
        "/users", data="{not json", content_type="application/json"
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "bad_request"


# --------------------------------------------------------------------------- #
# GET /users
# --------------------------------------------------------------------------- #
def test_list_users_empty_collection(client):
    response = client.get("/users")

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"] == []
    assert body["pagination"] == {
        "total": 0,
        "limit": 20,
        "offset": 0,
        "count": 0,
        "has_more": False,
    }


def test_list_users_returns_created_users(client, create_user):
    create_user(name="Ada", email="ada@example.com")
    create_user(name="Alan", email="alan@example.com")

    body = client.get("/users").get_json()

    assert [user["name"] for user in body["data"]] == ["Ada", "Alan"]
    assert body["pagination"]["total"] == 2
    assert body["pagination"]["has_more"] is False


def test_list_users_paginates(client, create_user):
    for index in range(5):
        create_user(name=f"User {index}", email=f"user{index}@example.com")

    body = client.get("/users?limit=2&offset=2").get_json()

    assert [user["name"] for user in body["data"]] == ["User 2", "User 3"]
    assert body["pagination"] == {
        "total": 5,
        "limit": 2,
        "offset": 2,
        "count": 2,
        "has_more": True,
    }


@pytest.mark.parametrize(
    "query", ["?limit=0", "?limit=101", "?limit=abc", "?offset=-1", "?offset=x"]
)
def test_list_users_rejects_invalid_pagination(client, query):
    response = client.get(f"/users{query}")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "validation_error"


# --------------------------------------------------------------------------- #
# Error envelope
# --------------------------------------------------------------------------- #
def test_unknown_route_returns_json_404(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "not_found"


def test_wrong_method_returns_json_405(client):
    response = client.delete("/users")

    assert response.status_code == 405
    assert response.get_json()["error"]["code"] == "method_not_allowed"
    assert "GET" in response.headers.get("Allow", "")
