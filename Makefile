.PHONY: install test lint db-up

VENV := backend/.venv

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

db-up:
	docker compose up -d --wait db

test: db-up
	cd backend && .venv/bin/pytest

lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint
