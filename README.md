## Literature Explorer

Make academic papers instantly scannable. Literature Explorer ingests papers from multiple sources, parses PDFs into structured sections, summarizes them, and exposes a fast search API with a minimal UI.

[![CI](https://github.com/Mister-JP/literature-explorer/actions/workflows/ci.yml/badge.svg)](https://github.com/Mister-JP/literature-explorer/actions/workflows/ci.yml)

### What you get
- Ingestion from arXiv, OpenAlex, Semantic Scholar, DOAJ, CORE, PMC
- License-aware PDF storage with no-serve enforcement
- PDF parsing via pdfminer or optional GROBID
- 3–5 sentence summaries (extractive) with 1000 char cap
- OpenSearch-backed search with optional semantic re-ranking
- REST API and a simple UI with inline summaries and expandable sections

### Prerequisites
- Python 3.10+
- Docker (optional, for local PostgreSQL and OpenSearch)
- Poetry (recommended) or pip
  - Optional: GROBID server (for high-accuracy parsing). Quickstart:
    - `docker run --rm -p 8070:8070 -e GROBID_MODE=service lfoppiano/grobid:0.8.0`
    - Set `PARSER_BACKEND=grobid` and optionally `GROBID_HOST=http://localhost:8070`

### Quickstart (2 minutes)
1) Install (pip):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

2) Configure environment:
```bash
cp .env.example .env
# Optionally edit .env to point at PostgreSQL or enable semantic ranking
```

3) Optional: start PostgreSQL locally (or use default SQLite):
```bash
docker compose up -d db
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/literature
```

4) Seed demo, index, and try the UI:
```bash
make seed-demo-ui
make reindex
make api   # visit http://localhost:8000/ui/search?q=transformer
```

5) Or run a search (choose one):
```bash
# Module entrypoint (no PYTHONPATH needed after editable install). Supports --author and --source (arxiv|openalex|semanticscholar).
python -m ingestion.cli run --query "transformer" --author "Vaswani" --max-results 3 --source arxiv
python -m ingestion.cli run --query "large language models" --max-results 3 --source openalex
python -m ingestion.cli run --query "transformers" --max-results 3 --source semanticscholar
python -m ingestion.cli run --query "climate change" --max-results 3 --source doaj

# or via Makefile
make run-search query="transformer" max=3
```

### Environment variables
Create a `.env` file with any overrides. Common options:
- `DATABASE_URL=sqlite:///./data/literature.db`
- `STORAGE_DIR=./data/pdfs`
- `ARXIV_MAX_RESULTS=10`
- Search: `SEARCH_HOST=http://localhost:9200`, `SEARCH_INDEX=papers`
- Parser: `PARSER_BACKEND=pdfminer|grobid`, `GROBID_HOST=http://localhost:8070`
- Semantics: `ENABLE_SEMANTIC=1`, `SEMANTIC_MODEL=sentence-transformers/all-MiniLM-L6-v2`, `SEMANTIC_TOPK=50`, `WEIGHT_SEMANTIC=1.0`, `WEIGHT_CITATIONS=0.2`, `WEIGHT_RECENCY=0.1`
- Providers: `CORE_API_KEY=...`, `OPENALEX_MAILTO=you@example.com`
To use PostgreSQL locally: `make db-up` or the docker compose command above, then set `DATABASE_URL` as shown.

### Output
JSON like `{ "stored": N, "skipped": M, "errors": E }`. Metadata stored in DB, PDFs under `data/pdfs/`.

### Architecture (high-level)
- Connectors fetch metadata and PDF URLs → `src/ingestion/connectors/*`
- Ingestion applies dedup + license checks and stores in DB → `src/ingestion/ingest.py`
- Parser builds sections via pdfminer or GROBID → `src/ingestion/parser*.py`
- Summarizer generates short summaries → `src/ingestion/summarizer.py`
- Indexer upserts into OpenSearch → `src/ingestion/indexer.py`
- API serves `/search`, `/paper/{id}`, `/summaries`, `/ui/search` → `src/ingestion/api.py`

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

Examples (curl):
```bash
curl -s 'http://localhost:8000/search?q=transformer&size=5' | jq '.hits[] | {id,title,year,summary}'
curl -s 'http://localhost:8000/paper/1' | jq '{title, license, has_sections: (.sections|length>0)}'
curl -s 'http://localhost:8000/summaries?q=climate%20change&size=3' | jq
```

Semantic re-ranking (optional):
- Enable via `ENABLE_SEMANTIC=1`
- Config via env: `SEMANTIC_MODEL`, `WEIGHT_SEMANTIC`, `WEIGHT_CITATIONS`, `WEIGHT_RECENCY`, `SEMANTIC_TOPK`
- When enabled, `/search` includes a `ranking_breakdown` per hit; `/paper/{id}` does not include ranking info.

### Minimal UI
- `GET /ui/search?q=...&size=20` renders a searchable table with:
  - Result header: total count, server latency (ms), active sort, and active filter badges
  - Filters: source, license, venue, year range, `has_summary` with URL sync ("thread" filter pending)
  - Zero-result empty state with guidance and a "Report this search" action (privacy-safe, hashed query)
  - Inline summaries (clamped with accessible "Show more" toggles)
  - Provenance under titles (source badge, DOI/arXiv/PMC links when available)
  - Row expanders to show parsed sections (Abstract, Methods, Results, Conclusion)
  - Star items locally and export visible/starred rows to CSV
  - Debug overlay showing last payload, count, latency, and sort

### Developer experience
- Pre-commit hooks: run `pre-commit` once, or `make pre-commit` to format and lint
- Secret scanning: gitleaks runs via pre-commit; do not commit `.env` or secrets
- Troubleshooting:
  - OpenSearch unavailable: run `make search-up` and verify `SEARCH_HOST`
  - GROBID not running: run `make grobid-up` or set `PARSER_BACKEND=pdfminer`
  - Summary missing: ensure `make parse-new` then `make summarize-new` (or `make retro-parse`)

#### Example: query -> summaries via CLI
```bash
# Start API in one terminal
make api

# In another terminal, fetch summaries for a query
curl -s 'http://localhost:8000/summaries?q=large%20language%20models&size=3' | jq
```

- `make lint` / `make format` / `make test`
