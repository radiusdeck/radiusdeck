.DEFAULT_GOAL := help
.PHONY: build up down logs reload health test-compose test test-community-artifact test-community-image

IMAGE_TAG ?= radiusdeck:latest

help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# ── Docker Compose ──────────────────────────────────────────
build: test-community-artifact ## Build the Community image from its tested wheel
	docker compose build

up: ## Start container in background
	docker compose up -d

down: ## Stop container
	docker compose down

logs: ## Show logs for containers
	docker compose logs -f --tail=100

test-compose: test-community-artifact ## Start the manual test stack
	docker compose -f docker-compose.test.yml up --build

# ── Quick checks ────────────────────────────────────────────
health: ## health
	@curl -sf http://localhost:8000/health | python -m json.tool

reload: ## post reload
	@curl -sf -X POST http://localhost:9090/reload \
		-H "Authorization: Bearer $$(grep RELOAD_TOKEN .env | cut -d= -f2)" \
		| python -m json.tool

# ── Development ─────────────────────────────────────────────
dev: ## start develop server
	APP_ENV=development APP_BACKUP_DIR="$${APP_BACKUP_DIR:-/tmp/radiusdeck/backups}" uvicorn radiusdeck.main:app --reload --host 0.0.0.0 --port 8000

lint: ## linting
	ruff check .
	black --check .
	mypy .
	bandit -q -r src

test: ## tests
	pytest tests/ -v

test-community-artifact: ## Build, inspect, install, and smoke-test Community wheel
	./scripts/test-community-artifact.sh

test-community-image: test-community-artifact ## Build and inspect Community image from tested wheel
	SKIP_ARTIFACT_TEST=true ./scripts/test-community-image.sh
