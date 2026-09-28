"""Application factory for the users microservice.

Usage::

    from app import create_app
    app = create_app("production")
"""

from __future__ import annotations

import time

from flask import Flask

from .api import register_blueprints
from .cli import register_cli
from .config import DEFAULT_SECRET_KEY, BaseConfig, resolve_config
from .extensions import db
from .logging_config import configure_logging
from .web import ui_bp

__version__ = "1.0.0"

__all__ = ["create_app", "db", "__version__"]


def create_app(config_object: str | type[BaseConfig] | None = None) -> Flask:
    """Build and configure a Flask application instance.

    :param config_object: ``"development" | "testing" | "production"``, a config
        class, or ``None`` to read the ``APP_ENV`` environment variable.
    """
    config_class = resolve_config(config_object)
    _validate_config(config_class)

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_class)

    configure_logging(app.config["LOG_LEVEL"], app.config["SERVICE_NAME"])
    app.extensions["service_start_monotonic"] = time.monotonic()

    # Importing the models registers them on ``db.metadata`` before create_all().
    from . import models  # noqa: F401

    db.init_app(app)
    register_blueprints(app)
    app.register_blueprint(ui_bp)
    register_cli(app)

    return app


def _validate_config(config_class: type[BaseConfig]) -> None:
    """Fail fast on a configuration that is unsafe for the target environment."""
    if config_class.ENV_NAME == "production" and (
        config_class.SECRET_KEY == DEFAULT_SECRET_KEY
    ):
        raise RuntimeError(
            "SECRET_KEY must be set to a unique value when running in production."
        )
