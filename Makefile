PY = python

.PHONY: setup install lint format test db-up db-down search-up up down run-search reindex api sweep hydrate-citations sweep-daemon bench pre-commit parse-new summarize-new retro-parse retry-parses grobid-up grobid-down sweep-core sweep-pmc coverage-counts seed-demo-ui ingest-pdf

setup:
	@echo "Poetry not detected; use pip install -r requirements.txt or install Poetry if desired."

install:
	poetry install --no-root

lint:
	. .venv/bin/activate && ruff check .

format:
	. .venv/bin/activate && black .

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

pre-commit:
	. .venv/bin/activate && pre-commit run --all-files

parse-new:
	PYTHONPATH=src $(PY) -m ingestion.cli parse-new

summarize-new:
	PYTHONPATH=src $(PY) -m ingestion.cli summarize-new

retro-parse:
	PYTHONPATH=src $(PY) -m ingestion.cli retro-parse

retry-parses:
	PYTHONPATH=src $(PY) -m ingestion.cli retry-parses $(if $(max_retries),--max-retries $(max_retries))

grobid-up:
	docker run --rm -d --name grobid -p 8070:8070 -e GROBID_MODE=service lfoppiano/grobid:0.8.0

grobid-down:
	docker rm -f grobid || true

sweep-core:
	PYTHONPATH=src $(PY) -m ingestion.cli run --query "$(or $(q), $(query))" --max-results $(or $(max), 10) --source core $(if $(author),--author "$(author)")

sweep-pmc:
	PYTHONPATH=src $(PY) -m ingestion.cli run --query "$(or $(q), $(query))" --max-results $(or $(max), 10) --source pmc $(if $(author),--author "$(author)")

coverage-counts:
	PYTHONPATH=src $(PY) -m ingestion.cli coverage-counts

seed-demo-ui:
	PYTHONPATH=src $(PY) -m ingestion.cli seed-demo-ui

ingest-pdf:
	PYTHONPATH=src $(PY) -m ingestion.cli ingest-pdf --url "$(url)" --title "$(title)" $(if $(source),--source "$(source)") $(if $(license),--license "$(license)") $(if $(year),--year $(year)) $(if $(authors),--authors "$(authors)")
