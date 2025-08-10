## Phase-1 Backend Foundations

This repository contains a minimal ingestion backend for academic literature, focused on arXiv for Phase-1. It can search arXiv, persist metadata to PostgreSQL, and download PDFs to local storage.

### Prerequisites
- Python 3.10+
- Docker (optional, for local PostgreSQL)
- Poetry (recommended) or pip
 - Optional: GROBID server (for high-accuracy parsing). Quickstart:
   - `docker run --rm -p 8070:8070 -e GROBID_MODE=service lfoppiano/grobid:0.8.0`
   - Set `PARSER_BACKEND=grobid` and optionally `GROBID_HOST=http://localhost:8070`

### Quickstart
1) Create a virtualenv and install dependencies (pip):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

2) Optional: start PostgreSQL locally (or use the default SQLite):
```bash
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/literature
```

3) Run a search (choose one):
```bash
# Module entrypoint (no PYTHONPATH needed after editable install). Supports --author and --source (arxiv|openalex|semanticscholar).
python -m ingestion.cli run --query "transformer" --author "Vaswani" --max-results 3 --source arxiv
python -m ingestion.cli run --query "large language models" --max-results 3 --source openalex
python -m ingestion.cli run --query "transformers" --max-results 3 --source semanticscholar
python -m ingestion.cli run --query "climate change" --max-results 3 --source doaj

# or via Makefile
make run-search query="transformer" max=3
```

Environment variables (defaults):
- `DATABASE_URL=sqlite:///./data/literature.db`
- `STORAGE_DIR=./data/pdfs`
- `ARXIV_MAX_RESULTS=10`
To use PostgreSQL locally: `make db-up` or the docker compose command above, then set `DATABASE_URL` as shown.

### Output
JSON like `{ "stored": N, "skipped": M, "errors": E }`. Metadata stored in DB, PDFs under `data/pdfs/`.

### Connector architecture
- Base interface in `src/ingestion/connectors/base.py` now uses `QuerySpec` and `PDFRef`.
- arXiv implementation in `src/ingestion/connectors/arxiv.py`.
- OpenAlex implementation in `src/ingestion/connectors/openalex.py`.
- Add new connectors by implementing `search(QuerySpec)` yielding `PaperMetadata` and optional `fetch_pdf`.
 - CORE connector requires `CORE_API_KEY` in the environment for live runs.

### Database schema
- Table `papers` includes: `id`, `source`, `external_id`, `doi`, `title`, `authors` (JSON), `abstract`, `license`, `pdf_path`, `fetched_at`.
- Deduplication: by DOI (preferred), then by `(source, external_id)`, then a heuristic hash of title + authors.

### CI
GitHub Actions runs linting (ruff, black) and tests (pytest) on each PR/push to `main`.

### Notes on licensing & compliance
- We normalize licenses (e.g., "CC BY 4.0" -> `cc-by`). PDFs are downloaded only for permissive licenses: `cc-*`, `cc0`, or `public-domain`. Others are treated as metadata-only.
  - Enforcement lives in `ingestion.utils.license_permits_pdf_storage` and is applied during ingestion.
  - The API also enforces a "no-serve" policy: `/paper/{id}` exposes `pdf_path` only when the license permits.

See `docs/license_policy.md` for details.

### Makefile targets
- `make db-up` / `make db-down`: start/stop PostgreSQL
- `make setup`: install dependencies via Poetry
- `make run-search query="..." max=10 [source=arxiv|openalex|semanticscholar|doaj]`: run ingestion
- `make search-up`: start OpenSearch
- `make up` / `make down`: start/stop DB and search together
- `make reindex`: push papers from DB into search index
- `make hydrate-citations seed=10.1007/s11263-015-0816-y depth=1`: simple citation chaining
  - Citation neighbors are fetched via OpenAlex (`ingestion.citations.fetch_openalex_neighbors`).
 - `make parse-new`: parse PDFs lacking parsed sections; stores `sections`, updates `abstract`/`conclusion`
 - `make summarize-new`: generate summaries for parsed papers
  - `make retro-parse`: backfill parse+summary across the corpus
    - Safety: `PYTHONPATH=src python -m ingestion.cli retro-parse --dry-run`
    - Backup: `PYTHONPATH=src python -m ingestion.cli retro-parse --backup-file backup.jsonl`
- `make retry-parses [max_retries=N]`: retry parsing failed items up to N attempts
- `make grobid-up` / `make grobid-down`: start/stop a local GROBID service

Parser selection:
- Default uses `pdfminer.six` heuristics.
- Set `PARSER_BACKEND=grobid` to use a running GROBID server (falls back to pdfminer on failure).

### Benchmarking search
- Ensure OpenSearch is up (`make search-up`), index documents (`make reindex`), then run `make bench`.
- `make api`: run the FastAPI server on `http://localhost:8000`
- `make sweep source=openalex q="large language models" max=20`: simple sweep convenience wrapper
- `make sweep source=core q="transformer" max=2` (live runs require `CORE_API_KEY`)
- `make sweep source=pmc q="transformer" max=2`
- `make sweep-core q="transformer" max=2` (requires `CORE_API_KEY` in environment for live runs)
- `make sweep-pmc q="transformer" max=2`
- `make coverage-counts`: print counts for PDFs with sections, abstract+conclusion, and summary

Recent local run example: `n=50 size=20 mean_ms=3.3 p95_ms=3.9` (your numbers will vary by hardware and index size).

### Phase-3 parse/summarize quick demo
1) Parse any unparsed PDFs:
```bash
make parse-new
```
2) Generate summaries for parsed papers:
```bash
make summarize-new
```
3) Backfill both across the corpus:
```bash
make retro-parse
```

### Search API
- `GET /search` with params: `q`, `author`, `year_start`, `year_end`, `license`, `source`, `sort=recency|citations`, `size`
- `GET /paper/{id}` returns metadata and PDF path if stored, plus `sections`, `conclusion`, `summary`.
- `GET /summaries?q=...&size=N` returns top summaries

Semantic re-ranking (optional):
- Enable via `ENABLE_SEMANTIC=1`
- Config via env: `SEMANTIC_MODEL`, `WEIGHT_SEMANTIC`, `WEIGHT_CITATIONS`, `WEIGHT_RECENCY`, `SEMANTIC_TOPK`
- When enabled, `/search` includes a `ranking_breakdown` per hit; `/paper/{id}` does not include ranking info.

### Minimal UI
- `GET /ui/search?q=...&size=20` renders a simple table with title, year, citation count, license badge, and inline summary. Rows can expand to show parsed sections (Abstract, Methods, Results, Conclusion) when available.

#### Example: query -> summaries via CLI
```bash
# Start API in one terminal
make api

# In another terminal, fetch summaries for a query
curl -s 'http://localhost:8000/summaries?q=large%20language%20models&size=3' | jq
```

- `make lint` / `make format` / `make test`


## Phase-2 Quickstart

1) Start services (DB + OpenSearch)

```bash
make up
```

2) Ingest from multiple sources

```bash
PYTHONPATH=src python -m ingestion.cli run --query "large language models" --max-results 10 --source openalex
PYTHONPATH=src python -m ingestion.cli run --query "transformers" --max-results 10 --source semanticscholar
PYTHONPATH=src python -m ingestion.cli run --query "climate change" --max-results 10 --source doaj
```

3) Reindex into OpenSearch

```bash
make reindex
```

4) Benchmark search

```bash
make bench  # target: p95 < 200ms for size=20
```

5) Run API and try queries

```bash
make api  # then visit http://localhost:8000/docs
```

6) Citation chaining (depth=1)

```bash
PYTHONPATH=src python -m ingestion.cli hydrate-citations 10.1038/nature14539 --depth 1 --max-per-level 25
```
