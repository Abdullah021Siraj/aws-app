"""Shared Flask extension instances.

Kept in their own module so models, blueprints and the app factory can import
them without creating circular imports.
"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

# Explicit naming convention keeps Alembic autogenerate stable if migrations
# are introduced later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
