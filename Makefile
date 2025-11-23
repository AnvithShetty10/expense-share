.PHONY: help build up down restart logs shell db-shell redis-shell migrate seed clean test lint format

# Default target
help:
	@echo "Expense Share - Available Commands:"
	@echo ""
	@echo "  Docker Commands:"
	@echo "    make build          - Build Docker images"
	@echo "    make up             - Start all services"
	@echo "    make down           - Stop all services"
	@echo "    make restart        - Restart all services"
	@echo "    make logs           - View logs from all services"
	@echo "    make logs-api       - View API logs"
	@echo "    make logs-db        - View database logs"
	@echo ""
	@echo "  Shell Commands:"
	@echo "    make shell          - Open shell in API container"
	@echo "    make db-shell       - Open PostgreSQL shell"
	@echo "    make redis-shell    - Open Redis CLI"
	@echo ""
	@echo "  Database Commands:"
	@echo "    make migrate        - Run database migrations"
	@echo "    make migrate-create - Create new migration (msg='description')"
	@echo "    make seed           - Seed database with test users"
	@echo "    make db-reset       - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "  Development Commands:"
	@echo "    make test           - Run all tests"
	@echo "    make test-unit      - Run unit tests only"
	@echo "    make test-integration - Run integration tests only"
	@echo "    make lint           - Run linters (flake8, mypy)"
	@echo "    make format         - Format code (black, isort)"
	@echo "    make clean          - Remove cache files and volumes"
	@echo ""
	@echo "  Quick Start:"
	@echo "    make build && make up"
	@echo ""

# Detect docker compose command
DOCKER_COMPOSE := $(shell \
    if command -v docker-compose >/dev/null 2>&1; then \
        echo "docker-compose"; \
    else \
        echo "docker compose"; \
    fi \
)

# Docker commands
build:
	$(DOCKER_COMPOSE) build

up:
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "✓ Services started!"
	@echo "  API:       http://localhost:8000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  Postgres:  localhost:5432"
	@echo "  Redis:     localhost:6379"
	@echo ""
	@echo "Run 'make logs' to view logs"

down:
	$(DOCKER_COMPOSE) down

restart:
	$(DOCKER_COMPOSE) restart

logs:
	$(DOCKER_COMPOSE) logs -f

logs-api:
	$(DOCKER_COMPOSE) logs -f api

logs-db:
	$(DOCKER_COMPOSE) logs -f postgres

# Shell commands
shell:
	$(DOCKER_COMPOSE) exec api /bin/bash

db-shell:
	$(DOCKER_COMPOSE) exec postgres psql -U postgres -d expense_share

redis-shell:
	$(DOCKER_COMPOSE) exec redis redis-cli

# Database commands
migrate:
	$(DOCKER_COMPOSE) exec api alembic upgrade head

migrate-create:
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a migration message: make migrate-create msg='your message'"; \
		exit 1; \
	fi
	$(DOCKER_COMPOSE) exec api alembic revision --autogenerate -m "$(msg)"

seed:
	$(DOCKER_COMPOSE) exec api python scripts/seed_database.py

db-reset:
	@echo "WARNING: This will delete all data in the database!"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) down -v; \
		$(DOCKER_COMPOSE) up -d postgres redis; \
		sleep 5; \
		$(DOCKER_COMPOSE) up -d api; \
		sleep 5; \
		make migrate; \
		make seed; \
		echo "Database reset complete!"; \
	fi

# Development commands
test:
	$(DOCKER_COMPOSE) exec api pytest

test-unit:
	$(DOCKER_COMPOSE) exec api pytest tests/unit -v

test-integration:
	$(DOCKER_COMPOSE) exec api pytest tests/integration -v

test-coverage:
	$(DOCKER_COMPOSE) exec api pytest --cov=app --cov-report=html --cov-report=term

lint:
	$(DOCKER_COMPOSE) exec api flake8 app tests
	$(DOCKER_COMPOSE) exec api mypy app

format:
	$(DOCKER_COMPOSE) exec api black app tests
	$(DOCKER_COMPOSE) exec api isort app tests

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	$(DOCKER_COMPOSE) down -v
	@echo "Cleaned up cache files and Docker volumes"
