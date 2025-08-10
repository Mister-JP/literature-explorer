PY = python

.PHONY: setup install lint format test db-up db-down search-up up down run-search reindex api sweep hydrate-citations sweep-daemon bench

setup:
	@echo "Poetry not detected; use pip install -r requirements.txt or install Poetry if desired."

install:
	poetry install --no-root

lint:
	@echo "Skipping lint (Poetry/linters not installed via pip)."

format:
	@echo "Skipping format (Poetry/linters not installed via pip)."

test:
	PYTHONPATH=src $(PY) -m pytest -q

db-up:
	docker compose up -d db

db-down:
	docker compose down

run-search:
	PYTHONPATH=src $(PY) -m ingestion.cli run --query "$(query)" --max-results $(or $(max), 10) --source $(or $(source), arxiv) $(if $(author),--author "$(author)")

search-up:
	docker compose up -d search

up:
	docker compose up -d db search

down:
	docker compose down

reindex:
	PYTHONPATH=src $(PY) -m ingestion.cli reindex

api:
	PYTHONPATH=src uvicorn ingestion.api:app --host 0.0.0.0 --port 8000

sweep:
	# Simple sweep against a source and query; author and max optional
	PYTHONPATH=src $(PY) -m ingestion.cli run --query "$(or $(q), $(query))" --max-results $(or $(max), 10) --source $(or $(source), arxiv) $(if $(author),--author "$(author)")

hydrate-citations:
	PYTHONPATH=src $(PY) -m ingestion.cli hydrate-citations $(if $(seed),"$(seed)") $(if $(depth),--depth $(depth))

sweep-daemon:
	PYTHONPATH=src $(PY) -m ingestion.cli sweep-daemon $(if $(file),--file $(file)) $(if $(interval),--interval $(interval)) $(if $(max_loops),--max-loops $(max_loops))

bench:
	PYTHONPATH=src $(PY) scripts/bench_search.py


