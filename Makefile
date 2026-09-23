.DEFAULT_GOAL := help

PYTHON ?= python3
# Containers write to backend/data as the host user.
export UID := $(shell id -u)
export GID := $(shell id -g)
VENV   := backend/.venv
BIN    := $(VENV)/bin

.PHONY: help install install-backend install-frontend dev backend frontend \
        test lint format typecheck check build up down clean db db-shell sync-catalog warm-cache llm-smoke \
        docker-sync-catalog docker-warm-cache demo logs

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Create venv and install backend deps
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e "backend[dev]"

install-frontend: ## Install frontend deps
	cd frontend && npm install

dev: db ## Run Postgres, backend and frontend together (Ctrl+C stops both)
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) --no-print-directory backend & \
	$(MAKE) --no-print-directory frontend & \
	wait

db: ## Start Postgres in Docker (:5432) and wait until ready
	docker compose up -d --wait db

db-shell: ## Open psql in the Postgres container
	docker compose exec db psql -U app -d ekt

sync-catalog: ## Download ekt.kz product list into backend/data/catalog.json
	cd backend && .venv/bin/python -m scripts.sync_catalog

warm-cache: ## Pre-load demo products and analogs into the detail cache
	cd backend && .venv/bin/python -m scripts.warm_cache

llm-smoke: ## Run the LLM assistant on demo questions (MODELS="gpt-4.1-mini gpt-5.4-mini")
	cd backend && .venv/bin/python -m scripts.llm_smoke $(MODELS)

backend: ## Run FastAPI on :8000 with reload
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend: ## Run Next.js on :3000
	cd frontend && npm run dev

test: ## Run backend tests
	cd backend && .venv/bin/pytest -q

lint: ## Lint backend and frontend
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

format: ## Auto-format backend code
	cd backend && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

typecheck: ## Type-check frontend
	cd frontend && npm run typecheck

check: lint typecheck test ## Everything CI would run

build: ## Production build of frontend
	cd frontend && npm run build

up: ## Run full stack in Docker (detached): db, backend :8000, frontend :3000
	docker compose up --build -d --wait
	@echo "Frontend: http://localhost:3000   Swagger: http://localhost:8000/docs"

down: ## Stop Docker stack
	docker compose down

logs: ## Follow Docker logs
	docker compose logs -f

docker-sync-catalog: ## sync-catalog inside Docker (writes backend/data/catalog.json)
	docker compose run --build --rm --no-deps backend python -m scripts.sync_catalog

docker-warm-cache: ## warm-cache inside Docker (writes backend/data/details_cache.sqlite)
	docker compose run --build --rm --no-deps backend python -m scripts.warm_cache

demo: ## Everything in Docker: sync catalog (if missing), warm cache, start the stack
	@test -f backend/data/catalog.json || $(MAKE) --no-print-directory docker-sync-catalog
	$(MAKE) --no-print-directory docker-warm-cache
	$(MAKE) --no-print-directory up

clean: ## Remove venv, node_modules and build output
	rm -rf $(VENV) frontend/node_modules frontend/.next backend/.pytest_cache backend/.ruff_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
