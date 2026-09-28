# Atheena AI Gateway — development commands.
# On VM 999 Postgres and Redis run natively (systemd); `make dev` only checks them.
# Elsewhere, `make dev USE_DOCKER=1` starts them from docker-compose.dev.yml first.

PYTHON ?= python3.12
VENV := backend/.venv
PY := $(CURDIR)/$(VENV)/bin/python
BIN := $(CURDIR)/$(VENV)/bin
COMPOSE := docker compose -f docker-compose.dev.yml
USE_DOCKER ?= 0

.DEFAULT_GOAL := help
.PHONY: help install dev down migrate seed test lint fmt run lock frontend create-key

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

$(VENV)/.installed: backend/pyproject.toml backend/requirements.lock
	@# Ubuntu without python3.12-venv lacks ensurepip: fall back to bootstrapping pip
	@# into a pip-less venv with the system pip (no sudo needed).
	$(PYTHON) -m venv $(VENV) >/dev/null 2>&1 || { rm -rf $(VENV) && \
		$(PYTHON) -m venv --without-pip $(VENV) && \
		$(PYTHON) -m pip --python $(VENV)/bin/python install -q pip; }
	$(PY) -m pip install -q -r backend/requirements.lock
	$(PY) -m pip install -q --no-deps -e backend
	touch $@

install: $(VENV)/.installed ## Create the backend venv with pinned dependencies

frontend/node_modules/.package-lock.json: frontend/package-lock.json
	cd frontend && npm ci
	touch $@

frontend: frontend/node_modules/.package-lock.json ## Install frontend deps and build
	cd frontend && npm run build

dev: install ## Install deps and check Postgres + Redis (USE_DOCKER=1 starts them first)
ifeq ($(USE_DOCKER),1)
	$(COMPOSE) up -d --wait
endif
	cd backend && $(PY) -m app.check_services

down: ## Stop docker dev services (no-op for native services)
ifeq ($(USE_DOCKER),1)
	$(COMPOSE) down
else
	@echo "Postgres and Redis run natively on this machine; nothing to stop."
endif

migrate: install ## Apply database migrations
	cd backend && $(BIN)/alembic upgrade head

seed: install ## Seed admin, sample member, project, settings, starter models
	cd backend && $(PY) -m app.seed

create-key: install ## Create an API key: make create-key EMAIL=user@example.com NAME=laptop
	@test -n "$(EMAIL)" -a -n "$(NAME)" || { echo "usage: make create-key EMAIL=... NAME=..."; exit 2; }
	cd backend && $(PY) -m app.cli create-key --email "$(EMAIL)" --name "$(NAME)"

test: install ## Run backend tests against the test database
	cd backend && $(BIN)/pytest

lint: install ## Lint and type-check backend, lint frontend
	cd backend && $(BIN)/ruff check . && $(BIN)/ruff format --check . && $(BIN)/mypy .
	@if [ -d frontend/node_modules ]; then cd frontend && npm run lint; \
		else echo "frontend/node_modules missing; run 'make frontend' to lint the frontend"; fi

fmt: install ## Auto-fix lint issues and format backend code
	cd backend && $(BIN)/ruff check --fix . && $(BIN)/ruff format .

run: install ## Run the API on http://127.0.0.1:8000 with auto-reload
	cd backend && $(BIN)/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log

lock: install ## Regenerate backend/requirements.lock after changing pyproject pins
	$(PY) -m pip install -q -e 'backend[dev]'
	{ echo "# Full pinned dependency set (direct + transitive). Regenerate with: make lock"; \
		$(PY) -m pip freeze --exclude-editable | grep -v -E '^(pip|setuptools)=='; } \
		> backend/requirements.lock
