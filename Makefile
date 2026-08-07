.PHONY: help up down build cli shell logs setup test lint clean

# ---------------------------------------------------------------------------
# AI Intigrate Coding - convenience shortcuts
#
# Docker (targets, no local Python needed):
#   make up                  # start the web frontend : http://localhost:5000
#   make cli TASK="<task>"   # run a task via the containerized agent
#   make down                # stop the frontend
#   make logs                # tail the frontend logs
#   make build               # rebuild the image after dependency changes
#   make shell               # open a shell inside the agent container
#
# Local (requires Python + Playwright):
#   make setup               # create .venv + install deps + Chromium
#   make test                # run the full test suite
#   make lint                # static type-check with pyright
#   make clean               # delete Python caches
#
# Examples:
#   make cli TASK="build a flask REST API with JWT auth"
# ---------------------------------------------------------------------------

COMPOSE = docker compose

help: ## List available commands.
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

up: ## Start the web frontend (http://localhost:5000).
	$(COMPOSE) up --build

down: ## Stop the frontend containers.
	$(COMPOSE) down

build: ## Rebuild the Docker images.
	$(COMPOSE) build

cli: ## Run a task in the container, e.g. make cli TASK="build a REST API".
	$(COMPOSE) run --rm cli $(TASK)

shell: ## Open a shell inside the agent container.
	$(COMPOSE) run --rm --entrypoint /bin/bash cli

logs: ## Tail the frontend logs.
	$(COMPOSE) logs -f

PY := $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python,python)
PYW := $(subst /,\,$(PY))

setup: ## Create .venv and install deps + Chromium.
	python -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m playwright install chromium

test: ## Run the full test suite.
	$(PY) -m pytest tests frontend/tests -q

lint: ## Static type-check with pyright.
	$(PY) -m pyright

clean: ## Remove Python build/cache artifacts.
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null; \
	rm -rf .pytest_cache .mypy_cache .ruff_cache