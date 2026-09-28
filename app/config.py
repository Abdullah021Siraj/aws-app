"""Environment driven configuration for the users microservice."""

from __future__ import annotations

import os
from typing import Any

# 5433 matches the host port published by docker-compose.yml.
DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5433/users_db"


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise RuntimeError(f"Environment variable {name}={raw!r} is not an integer") from exc


def normalize_database_url(url: str) -> str:
    """Force the psycopg (v3) driver and accept the common URL aliases."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def build_engine_options(uri: str) -> dict[str, Any]:
    """Engine options tuned for a connection-pooled web service.

    ``connect_timeout`` goes into ``connect_args`` because it is a libpq/driver
    level option; SQLAlchemy rejects unknown top level engine arguments.
    """
    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": _get_int("DB_POOL_SIZE", 5),
        "max_overflow": _get_int("DB_MAX_OVERFLOW", 10),
        "pool_recycle": _get_int("DB_POOL_RECYCLE", 1800),
        "pool_timeout": _get_int("DB_POOL_TIMEOUT", 10),
        "connect_args": {"connect_timeout": _get_int("DB_CONNECT_TIMEOUT", 5)},
    }
    # In-memory SQLite (tests) needs a single shared connection.
    if uri.startswith("sqlite"):
        return {"pool_pre_ping": True}
    return options


DEFAULT_SECRET_KEY = "insecure-development-key"


class BaseConfig:
    """Settings shared by every environment."""

    ENV_NAME = "base"

    SERVICE_NAME = os.getenv("SERVICE_NAME", "users-service")
    API_VERSION = os.getenv("API_VERSION", "v1")
    APP_VERSION = "1.0.0"

    SECRET_KEY = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
    # The HTML pages use a signed session cookie for CSRF tokens and flashes.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    PERMANENT_SESSION_LIFETIME = _get_int("SESSION_LIFETIME", 1800)

    TESTING = False
    DEBUG = False

    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = build_engine_options(SQLALCHEMY_DATABASE_URI)

    # Pagination defaults for collection endpoints.
    DEFAULT_PAGE_SIZE = _get_int("DEFAULT_PAGE_SIZE", 20)
    MAX_PAGE_SIZE = _get_int("MAX_PAGE_SIZE", 100)

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    JSON_SORT_KEYS = False


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = True


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    )
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = build_engine_options(
        SQLALCHEMY_DATABASE_URI
    )
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def resolve_config(config_object: str | type[BaseConfig] | None) -> type[BaseConfig]:
    """Resolve a config name/object; defaults to ``APP_ENV`` or development."""
    if config_object is None:
        config_object = os.getenv("APP_ENV", "development")
    if isinstance(config_object, str):
        try:
            return CONFIGS[config_object.lower()]
        except KeyError as exc:
            valid = ", ".join(sorted(CONFIGS))
            raise RuntimeError(
                f"Unknown configuration '{config_object}'. Valid values: {valid}"
            ) from exc
    return config_object
