APP_ENV ?= development
COMPOSE ?= docker compose

.PHONY: help install install-hooks uninstall-hooks run test test-all lint db-init db-seed db-shell docker-build docker-up docker-down docker-logs clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Create a venv and install dev dependencies
	python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

install-hooks:  ## Activate the pre-push test gate (runs on every git push)
	git config core.hooksPath .githooks
	@echo "pre-push hook active. Bypass with: git push --no-verify"

uninstall-hooks:  ## Remove the pre-push test gate
	git config --unset core.hooksPath || true
	@echo "pre-push hook removed"

run:  ## Run the dev server on :8000
	flask --app app.wsgi:application run --host 0.0.0.0 --port 8000 --debug

test:  ## Run the unit tests (in-memory SQLite)
	pytest

test-all:  ## Run unit tests plus the PostgreSQL integration tests
	pytest -m "not integration" && TEST_DATABASE_URL=$${TEST_DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:5433/users_db_test} pytest -m integration

db-init:  ## Create missing tables
	flask --app app.wsgi:application init-db

db-seed:  ## Insert demo users
	flask --app app.wsgi:application seed-db

db-shell:  ## Open a psql shell against the local database
	psql "$${DATABASE_URL:-postgresql://postgres:postgres@localhost:5433/users_db}"

docker-build:  ## Build the API image
	$(COMPOSE) build

docker-up:  ## Start postgres + api in the background
	$(COMPOSE) up -d --build && $(COMPOSE) ps

docker-down:  ## Stop the stack (add VOLUMES=1 to delete data)
	$(COMPOSE) down $(if $(VOLUMES),--volumes,)

docker-logs:  ## Tail API logs
	$(COMPOSE) logs -f api

clean:  ## Remove caches and build artefacts
	rm -rf .pytest_cache .coverage htmlcov **/__pycache__
