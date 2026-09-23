.DEFAULT_GOAL := help

PYTHON ?= python3
VENV   := backend/.venv
BIN    := $(VENV)/bin

.PHONY: help install install-backend install-frontend dev backend frontend \
        test lint format typecheck check build up down clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install all dependencies

install-backend: ## Create venv and install backend deps
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -e "backend[dev]"

install-frontend: ## Install frontend deps
	cd frontend && npm install

dev: ## Run backend and frontend together (Ctrl+C stops both)
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) --no-print-directory backend & \
	$(MAKE) --no-print-directory frontend & \
	wait

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

up: ## Run full stack in Docker
	docker compose up --build

down: ## Stop Docker stack
	docker compose down

clean: ## Remove venv, node_modules and build output
	rm -rf $(VENV) frontend/node_modules frontend/.next backend/.pytest_cache backend/.ruff_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
