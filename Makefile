.PHONY: init up down logs lint typecheck test fmt openapi run seed

init:
python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .
. .venv/bin/activate && pip install -U ruff mypy pytest

up:
docker compose up -d --build

down:
docker compose down -v

logs:
docker compose logs -f app

lint:
. .venv/bin/activate && ruff check .

fmt:
. .venv/bin/activate && ruff format .

typecheck:
. .venv/bin/activate && mypy apps

test:
. .venv/bin/activate || true ; pytest

openapi:
@echo "OpenAPI: ./openapi.yaml"

run:
docker compose up app

seed:
@echo "TODO: seed script"
