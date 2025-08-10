PY = python

.PHONY: setup install lint format test db-up db-down run-search

setup:
	@echo "Poetry not detected; use pip install -r requirements.txt or install Poetry if desired."

install:
	poetry install --no-root

lint:
	@echo "Skipping lint (Poetry/linters not installed via pip)."

format:
	@echo "Skipping format (Poetry/linters not installed via pip)."

test:
	@echo "Skipping tests (pytest not installed via pip)."

db-up:
	docker compose up -d db

db-down:
	docker compose down

run-search:
	PYTHONPATH=src $(PY) -m ingestion.cli --query "$(query)" --max-results $(or $(max), 10)


