"""Tests for GET /health."""

from __future__ import annotations

from app.api import health as health_module


def test_health_reports_ok_with_database_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "users-service"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["database"]["latency_ms"] >= 0
    assert body["uptime_seconds"] >= 0


def test_health_returns_503_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(
        health_module,
        "check_database",
        lambda: ("error", 1.5, "OperationalError"),
    )

    response = client.get("/health")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"]["status"] == "error"


def test_health_sets_correlation_headers(client):
    response = client.get("/health", headers={"X-Request-ID": "req-123"})

    assert response.headers["X-Request-ID"] == "req-123"
    assert response.headers["X-Service-Name"] == "users-service"


def test_health_generates_request_id_when_missing(client):
    response = client.get("/health")

    assert response.headers["X-Request-ID"]
