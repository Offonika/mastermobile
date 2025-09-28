.PHONY: init up down logs lint typecheck test fmt openapi db-upgrade db-downgrade run seed worker \
	docs-markdownlint docs-links docs-spellcheck docs-ci docs-ci-smoke

VENV_DIR := .venv
VENV_BIN := $(VENV_DIR)/bin
PYTHON := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip
RUFF := $(VENV_BIN)/ruff
MYPY := $(VENV_BIN)/mypy
PYTEST := $(VENV_BIN)/pytest
VENV_SENTINEL := $(VENV_DIR)/.initialized
MARKDOWNLINT_IMAGE := ghcr.io/igorshubovych/markdownlint-cli:0.39.0
LYCHEE_IMAGE := ghcr.io/lycheeverse/lychee:latest
MARKDOWNLINT_TARGETS ?= '**/*.md'
LYCHEE_TARGETS ?= README.md docs/
DOCS_SMOKE_DIR := build/docs-ci-smoke

init: $(VENV_SENTINEL)

$(VENV_SENTINEL): pyproject.toml
	@test -d $(VENV_DIR) || python -m venv $(VENV_DIR)
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

docs-markdownlint:
	docker run --rm -v "$(CURDIR)":/workdir -w /workdir $(MARKDOWNLINT_IMAGE) \
	  --config .markdownlint.yml $(MARKDOWNLINT_TARGETS)

docs-links:
	docker run --rm -v "$(CURDIR)":/workdir -w /workdir $(LYCHEE_IMAGE) \
	  --config /workdir/.lychee.toml --no-progress $(LYCHEE_TARGETS)

docs-spellcheck: $(VENV_SENTINEL)
	$(VENV_BIN)/codespell --config .codespellrc --check-hidden --check-filenames

docs-ci: docs-markdownlint docs-links docs-spellcheck

docs-ci-smoke:
	command -v docker >/dev/null 2>&1 || { echo "Docker is required for docs-ci-smoke." >&2; exit 2; }
	rm -rf "$(DOCS_SMOKE_DIR)"
	mkdir -p "$(DOCS_SMOKE_DIR)"
	printf '# Docs CI smoke test\n\n# This temporary file ensures lychee fails on an unreachable link.\n\n[broken](https://example.invalid/mastermobile-smoke)\n' > "$(DOCS_SMOKE_DIR)/broken.md"
	$(MAKE) --no-print-directory docs-links LYCHEE_TARGETS="$(DOCS_SMOKE_DIR)/broken.md" > "$(DOCS_SMOKE_DIR)/lychee.log" 2>&1; \
	status=$$?; \
	if [ $$status -eq 0 ]; then \
		cat "$(DOCS_SMOKE_DIR)/lychee.log"; \
		echo "Expected docs-links to fail when checking a broken URL." >&2; \
		rm -rf "$(DOCS_SMOKE_DIR)"; \
		exit 1; \
	elif ! grep -q 'example.invalid/mastermobile-smoke' "$(DOCS_SMOKE_DIR)/lychee.log"; then \
		cat "$(DOCS_SMOKE_DIR)/lychee.log"; \
		echo "docs-links failed but did not report the smoke link; check the environment." >&2; \
		rm -rf "$(DOCS_SMOKE_DIR)"; \
		exit 1; \
	else \
		rm -rf "$(DOCS_SMOKE_DIR)"; \
		echo "Lychee correctly detected a broken link."; \
	fi

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
