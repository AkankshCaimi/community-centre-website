.PHONY: install test lint db-up ci

VENV := backend/.venv

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

db-up:
	docker compose up -d --wait db

test: db-up
	cd backend && .venv/bin/pytest
	cd frontend && npm test

lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && npm run lint

# The checks GitHub Actions runs, on a fresh database. See docs/ci.md.
ci:
	scripts/ci.sh all
