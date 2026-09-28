"""Tests for the server rendered pages under /ui."""

from __future__ import annotations

import re

import pytest

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf_from(client, path: str = "/ui/users/new") -> str:
    match = CSRF_RE.search(client.get(path).get_data(as_text=True))
    assert match, "the form did not render a CSRF token"
    return match.group(1)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def test_root_redirects_to_dashboard(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].rstrip("/").endswith("/ui")


def test_dashboard_renders_health_and_totals(client, create_user):
    create_user(name="Ada", email="ada@example.com")

    response = client.get("/ui")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "users-service" in body
    assert "OK" in body  # database panel
    assert "Ada" in body  # latest user
    assert "1" in body


def test_dashboard_survives_an_empty_database(client):
    response = client.get("/ui")

    assert response.status_code == 200
    assert "No users yet" in response.get_data(as_text=True)


def test_users_page_lists_rows(client, create_user):
    create_user(name="Ada", email="ada@example.com")
    create_user(name="Alan", email="alan@example.com")

    response = client.get("/ui/users")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "ada@example.com" in body
    assert "alan@example.com" in body
    assert "1&ndash;2 of 2" in body


def test_users_page_paginates(client, create_user):
    for index in range(3):
        create_user(name=f"User {index}", email=f"user{index}@example.com")

    body = client.get("/ui/users?limit=2&offset=2").get_data(as_text=True)

    assert "user2@example.com" in body
    assert "user0@example.com" not in body
    assert "Next" in body


def test_users_page_rejects_invalid_pagination(client):
    response = client.get("/ui/users?limit=abc")

    assert response.status_code == 400
    assert "must be a number" in response.get_data(as_text=True)


def test_stylesheet_is_served(client):
    response = client.get("/static/css/app.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["Content-Type"]


# --------------------------------------------------------------------------- #
# Creating through the form
# --------------------------------------------------------------------------- #
def test_form_post_creates_user_and_redirects(client):
    token = _csrf_from(client)

    response = client.post(
        "/ui/users",
        data={"csrf_token": token, "name": "Grace Hopper", "email": "grace@example.com"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/ui/users")

    listing = client.get("/ui/users").get_data(as_text=True)
    assert "grace@example.com" in listing
    assert "Created Grace Hopper" in listing  # flash message


def test_form_post_rejects_missing_csrf_token(client):
    response = client.post(
        "/ui/users", data={"name": "Mallory", "email": "mallory@example.com"}
    )

    assert response.status_code == 400
    assert "CSRF" in response.get_data(as_text=True)

    listing = client.get("/ui/users").get_data(as_text=True)
    assert "mallory@example.com" not in listing


def test_form_post_rejects_forged_csrf_token(client):
    _csrf_from(client)  # establishes a session, then we send a wrong token

    response = client.post(
        "/ui/users",
        data={"csrf_token": "not-the-right-token", "name": "Mallory", "email": "m@example.com"},
    )

    assert response.status_code == 400


def test_form_post_shows_validation_errors(client):
    token = _csrf_from(client)

    response = client.post(
        "/ui/users", data={"csrf_token": token, "name": "", "email": "nope"}
    )

    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "name" in body and "required" in body
    assert "not a valid email" in body


def test_form_post_reports_duplicate_email(client, create_user):
    create_user(name="Ada", email="ada@example.com")
    token = _csrf_from(client)

    response = client.post(
        "/ui/users", data={"csrf_token": token, "name": "Ada", "email": "ada@example.com"}
    )

    assert response.status_code == 409
    assert "already exists" in response.get_data(as_text=True)


# --------------------------------------------------------------------------- #
# Error pages, and the JSON API staying untouched
# --------------------------------------------------------------------------- #
def test_unknown_ui_page_renders_html_error(client):
    response = client.get("/ui/nope")

    assert response.status_code == 404
    assert "text/html" in response.headers["Content-Type"]
    assert "Not Found" in response.get_data(as_text=True)


def test_api_routes_still_return_json(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"

    listing = client.get("/users")
    assert listing.status_code == 200
    assert listing.get_json()["data"] == []

    unknown = client.get("/definitely-not-a-route")
    assert unknown.status_code == 404
    assert unknown.get_json()["error"]["code"] == "not_found"


def test_api_create_user_needs_no_csrf_token(client):
    """The JSON API is stateless; CSRF protection applies to browser forms only."""
    response = client.post(
        "/users", json={"name": "Ada", "email": "ada@example.com"}
    )

    assert response.status_code == 201


@pytest.mark.parametrize("path", ["/ui/users", "/ui/users/new"])
def test_pages_never_mutate_state_on_get(client, path):
    before = client.get("/users").get_json()["pagination"]["total"]

    assert client.get(path).status_code == 200
    assert client.get("/users").get_json()["pagination"]["total"] == before
