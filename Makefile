.PHONY: init up down logs lint typecheck test fmt openapi db-upgrade db-downgrade run seed worker

VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
RUFF := $(VENV_BIN)/ruff
MYPY := $(VENV_BIN)/mypy
PYTEST := $(VENV_BIN)/pytest
VENV_SENTINEL := $(VENV_DIR)/.initialized

init: $(VENV_SENTINEL)

$(VENV_SENTINEL): pyproject.toml
	test -d $(VENV_DIR) || python -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	touch $(VENV_SENTINEL)

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f app

lint: $(VENV_SENTINEL)
	$(RUFF) check .

fmt: $(VENV_SENTINEL)
	$(RUFF) format .

typecheck: $(VENV_SENTINEL)
	$(MYPY) apps

test: $(VENV_SENTINEL)
	$(PYTEST)

openapi:
	@echo "OpenAPI: ./openapi.yaml"

db-upgrade: $(VENV_SENTINEL)
	$(VENV_BIN)/alembic -c apps/mw/migrations/alembic.ini upgrade head

db-downgrade: $(VENV_SENTINEL)
	$(VENV_BIN)/alembic -c apps/mw/migrations/alembic.ini downgrade -1

run:
	docker compose up app

seed:
	@echo "TODO: seed script"

worker:
	docker compose up stt-worker
