# users-service

A Flask + PostgreSQL microservice exposing a health probe and a user collection,
plus a small server-rendered web UI for browsing and creating users.

| Method | Path              | Purpose                                  |
| ------ | ----------------- | ---------------------------------------- |
| `GET`  | `/health`         | Readiness probe, incl. a database check  |
| `GET`  | `/users`          | List users with offset pagination        |
| `POST` | `/users`          | Create a user                            |
| `GET`  | `/`               | Redirects to the dashboard               |
| `GET`  | `/ui`             | Dashboard: health, totals, latest users  |
| `GET`  | `/ui/users`       | User table with pagination               |
| `POST` | `/ui/users`       | Create a user from the HTML form         |
| `GET`  | `/ui/users/new`   | Create form (GET a CSRF token here)      |

The JSON API and the HTML pages coexist: the UI lives under `/ui` (and `/`),
so `GET /users` and `POST /users` remain pure JSON for other services.

## Stack

- Python 3.12, Flask 3, Flask-SQLAlchemy 3, SQLAlchemy 2 (ORM style)
- PostgreSQL 16 via `psycopg` 3
- Jinja templates + one hand-written stylesheet for the web UI, no frontend build step
- Gunicorn (gthread) in the container, Flask's reloader in development
- pytest for unit tests plus optional integration tests against real PostgreSQL

## Quick start with Docker

```bash
cp .env.example .env          # set SECRET_KEY
make docker-up                 # postgres on :5433, api on :8000
curl -s localhost:8000/health
```

The container runs `flask init-db` before Gunicorn, so the schema is created on
boot. The API and the web UI are both served on `http://localhost:8000`.

Open <http://localhost:8000/ui> in a browser for the dashboard, or
<http://localhost:8000/ui/users> to browse and create users.

Tear down with `make docker-down` (or `make docker-down VOLUMES=1` to also drop
the database volume).

## Local development

```bash
make install                    # venv + requirements-dev.txt
cp .env.example .env
docker compose up -d db         # just the database
make db-init && make db-seed    # create tables, insert demo users
make run                        # dev server on :8000 with reloader
```

Point `DATABASE_URL` at any PostgreSQL instance. The scheme must use the psycopg
driver (`postgresql+psycopg://`); plain `postgres://` URLs are upgraded
automatically.

## API

### `GET /health`

`200` when the service and its database are healthy, `503` when the database is
unreachable, so it works as both a liveness and a readiness probe.

```json
{
  "status": "ok",
  "service": "users-service",
  "version": "1.0.0",
  "api_version": "v1",
  "uptime_seconds": 1.043,
  "checks": { "database": { "status": "ok", "latency_ms": 2.31 } }
}
```

### `GET /users`

Query parameters: `limit` (default 20, max 100) and `offset` (default 0).
Invalid values return `400`.

```json
{
  "data": [
    {
      "id": 1,
      "name": "Ada Lovelace",
      "email": "ada@example.com",
      "created_at": "2026-09-28T09:54:23.031150+00:00",
      "updated_at": "2026-09-28T09:54:23.031150+00:00"
    }
  ],
  "pagination": { "total": 1, "limit": 20, "offset": 0, "count": 1, "has_more": false }
}
```

### `POST /users`

Requires `Content-Type: application/json`. `name` and `email` are required,
`email` is lowercased and must be unique.

```bash
curl -X POST localhost:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"name": "Ada Lovelace", "email": "ada@example.com"}'
```

`201 Created`:

```json
{ "data": { "id": 1, "name": "Ada Lovelace", "email": "ada@example.com", "...": "..." } }
```

## Web UI

Server-rendered pages, no build step and no JavaScript framework. Open
`/ui` for the dashboard, `/ui/users` for the paginated table, `/ui/users/new`
for the create form.

- Both pages call the same service layer as the API, so behaviour matches.
- Form posts are protected with a per-session CSRF token (`itsdangerous`
  signed cookie); missing or forged tokens return `400`.
- Validation and duplicate-email errors are re-rendered inline with the
  offending values preserved (`400` for validation, `409` for duplicates).
- Success uses Post/Redirect/Get with a one-shot flash message, so a refresh
  never re-submits the form.
- `/ui/*` and `/` render HTML error pages; every other path returns the JSON
  error envelope, so the API contract is unaffected.
- No auth: the UI is for local use or a trusted network. Put it behind a
  gateway before exposing it.

## Status codes and errors

| Code | When                                                    |
| ---- | ------------------------------------------------------- |
| 200  | `GET /health` healthy, `GET /users` listed             |
| 201  | User created                                            |
| 303  | Form post succeeded, redirect to the user list          |
| 400  | Validation failure, malformed JSON body, or bad CSRF    |
| 404  | Unknown route                                           |
| 405  | Wrong method on a known route                           |
| 409  | Email already exists                                    |
| 415  | `POST /users` without a JSON content type               |
| 503  | Database unavailable, or `GET /health` degraded         |

Every API error uses the same envelope, with per-field detail where relevant:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": [{ "field": "email", "message": "'email' is not a valid email address." }]
  }
}
```

Codes: `validation_error`, `duplicate_email`, `database_unavailable`,
`not_found`, `method_not_allowed`, `unsupported_media_type`, `bad_request`,
`internal_server_error`.

## Response headers

Every response carries `X-Request-ID` (echoed from an inbound header when
present) and `X-Service-Name`, so requests can be traced across services.

## Configuration

All settings come from the environment; see `.env.example` for the full list.
The most relevant ones:

| Variable                                   | Default                 | Notes                                    |
| ------------------------------------------ | ----------------------- | ---------------------------------------- |
| `APP_ENV`                                  | `development`           | `development`, `testing`, `production`   |
| `DATABASE_URL`                             | local `users_db`        | `postgresql+psycopg://user:pass@host/db` |
| `SECRET_KEY`                               | insecure dev value      | Required in production, boot fails without |
| `LOG_LEVEL`                                | `INFO`                  | JSON logs on stdout                      |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`         | 5 / 10                  | Per gunicorn worker                      |
| `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE`      | 20 / 100                | `GET /users` bounds                      |
| `WEB_CONCURRENCY`                          | `2 * cores + 1`         | Gunicorn workers                         |

`APP_ENV=production` refuses to start on the default `SECRET_KEY`.

## CLI commands

```bash
flask --app app.wsgi:application init-db   # create missing tables (idempotent)
flask --app app.wsgi:application seed-db   # insert demo users
flask --app app.wsgi:application check-db  # verify connectivity
flask --app app.wsgi:application drop-db   # drop all tables (destructive)
```

## Tests

```bash
make test      # unit tests on in-memory SQLite, no setup needed
make test-all  # also runs the PostgreSQL integration tests
```

Integration tests are skipped unless `TEST_DATABASE_URL` is set:

```bash
docker compose exec db psql -U postgres -c "CREATE DATABASE users_db_test;"
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/users_db_test \
  pytest -m integration
```

## Layout

```
app/
  __init__.py       application factory (create_app)
  config.py         environment driven configuration
  extensions.py     SQLAlchemy instance
  logging_config.py JSON logging
  validation.py     request payload validation
  cli.py            init-db / seed-db / check-db / drop-db
  wsgi.py           gunicorn entrypoint
  models/           User ORM model
  api/
    health.py       GET /health
    users.py        GET /users, POST /users
    errors.py       ApiError, JSON and HTML error handlers
  web/
    views.py        dashboard, user list, create form
    forms.py        CSRF tokens and flash messages
  templates/        Jinja templates (base, dashboard, users, form, error)
  static/css/       single stylesheet
tests/              unit + integration tests
Dockerfile          multi-stage, non-root, healthcheck
docker-compose.yml  api + postgres
gunicorn.conf.py    production server settings
```

## Notes and limitations

- Schema management uses `db.create_all()`, which creates missing tables but
  does not alter existing ones. For production, introduce Alembic
  (`Flask-Migrate`) before the first breaking schema change.
- The `users` table is the service's own data. In a real microservice
  deployment other services would reach it through events or an API, never by
  sharing this database.
- The list endpoint uses offset pagination. At large offsets consider switching
  to keyset pagination on `(created_at, id)`, which the existing index supports.
- No authentication or rate limiting is implemented; put the service behind
  an API gateway if it is exposed outside a trusted network. The web UI is
  likewise unauthenticated.
- The web UI has no JavaScript, so the per-page "per page" selector needs
  `noscript` submit or an Enter key. Add a small script if you want full
  interactivity.
