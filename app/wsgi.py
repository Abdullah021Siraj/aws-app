"""WSGI entrypoint: ``gunicorn app.wsgi:application``."""

from __future__ import annotations

from . import create_app

application = create_app()
app = application  # convenience alias for ``flask --app app.wsgi run``

if __name__ == "__main__":  # pragma: no cover
    application.run(host="0.0.0.0", port=8000)
