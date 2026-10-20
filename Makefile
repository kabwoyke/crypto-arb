.PHONY: up down test test-int lint fmt migrate sim

up:
	docker compose up -d --wait

down:
	docker compose down

test:
	uv run pytest -m "not integration"

test-int:
	uv run pytest -m integration

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

fmt:
	uv run ruff check --fix .
	uv run ruff format .

migrate:
	@echo "Alembic is introduced in Phase 1 (ledger schema); nothing to migrate yet."

sim:
	@echo "Exchange simulator lands in Phase 2."
