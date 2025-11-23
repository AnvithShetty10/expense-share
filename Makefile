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

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d
	@echo ""
	@echo "✓ Services started!"
	@echo "  API:       http://localhost:8000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  Postgres:  localhost:5432"
	@echo "  Redis:     localhost:6379"
	@echo ""
	@echo "Run 'make logs' to view logs"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-db:
	docker-compose logs -f postgres

# Shell commands
shell:
	docker-compose exec api /bin/bash

db-shell:
	docker-compose exec postgres psql -U postgres -d expense_share

redis-shell:
	docker-compose exec redis redis-cli

# Database commands
migrate:
	docker-compose exec api alembic upgrade head

migrate-create:
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a migration message: make migrate-create msg='your message'"; \
		exit 1; \
	fi
	docker-compose exec api alembic revision --autogenerate -m "$(msg)"

seed:
	docker-compose exec api python scripts/seed_database.py

db-reset:
	@echo "WARNING: This will delete all data in the database!"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		docker-compose up -d postgres redis; \
		sleep 5; \
		docker-compose up -d api; \
		sleep 5; \
		make migrate; \
		make seed; \
		echo "Database reset complete!"; \
	fi

# Development commands
test:
	docker-compose exec api pytest

test-unit:
	docker-compose exec api pytest tests/unit -v

test-integration:
	docker-compose exec api pytest tests/integration -v

test-coverage:
	docker-compose exec api pytest --cov=app --cov-report=html --cov-report=term

lint:
	docker-compose exec api flake8 app tests
	docker-compose exec api mypy app

format:
	docker-compose exec api black app tests
	docker-compose exec api isort app tests

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	docker-compose down -v
	@echo "Cleaned up cache files and Docker volumes"
