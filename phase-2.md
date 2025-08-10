# Phase-2: Discovery Expansion & Search Index — Goal & Checklist

**Objective**
Expand beyond arXiv with a plug-in connector pattern, introduce a real search index for fast retrieval, and support richer queries (keyword, author, and first pass at citation chaining). The outcome is a broader, faster corpus that remains legally safe and deduped.

---

## 🎯 Deliverables

### Status snapshot (in repo)

- Connector base plus arXiv, OpenAlex, Semantic Scholar, and DOAJ implemented; ingestion → DB working with dedup and license gate; OpenSearch + indexer + API live. Author/year filters and license filter validated; citations sort validated; citation chaining MVP and sweep-daemon added.
- Live conformance runs supported for OpenAlex and Semantic Scholar; DOAJ optional (API variance) and can be enabled with `INCLUDE_DOAJ=1` for live tests. Cassettes are present for OpenAlex/Semantic Scholar.
- License policy doc added and enforced in ingestion + API.
- Search benchmarking script present (`scripts/bench_search.py`); target <200ms p95 expected on dev corpus when index is warmed. Local numbers will vary by environment.

- [x] **Connector Framework (Production-Ready)**
  - [x] Finalize `BaseConnector` interface (type hints + docstrings) with methods:
        `search(query: QuerySpec) -> Iterable[PaperMetadata]`, `fetch_pdf(item: PaperMetadata) -> Optional[PDFRef]`.
  - [ ] Shared utilities:
        - [x] Backoff/retry (downloader)
        - [x] Per-source rate limits utility
        - [x] Telemetry hooks
        - [x] License extractor/normalizer
  - [x] Connector conformance tests (pytest) with a small cassette-based suite (e.g., `vcrpy`) and/or live runs.
    - [x] OpenAlex and Semantic Scholar recorded/live supported
    - [x] DOAJ recorded (optional; enable via `INCLUDE_DOAJ=1`)

- [x] **New Connectors (at least two of the following)**
  - [x] **OpenAlex**: keyword + author queries; pull DOI, concepts, citations, license where available. (initial implementation; refine author filter, surface OA PDF URL)
  - [x] **Semantic Scholar** (open endpoints): metadata enrichment (citations, influential citations).
  - [x] **DOAJ** (Directory of Open Access Journals): metadata + OA status.
  - [ ] **CORE**: OA metadata and PDF links (respecting license).
  - [ ] **PubMed/PMC**: E-utilities for metadata; PMC OA subset for PDFs and license tags.
  - [ ] Each connector:
        - [x] Honors legal/licensing fields and stores a normalized `license` string (normalization enforced in ingestion layer).
        - [x] Emits `(source, external_id)` and DOI for dedup.
        - [x] Returns consistent `PaperMetadata` with `sections` empty (parsing is Phase-3).

- [x] **Search Index**
  - [x] Stand up **OpenSearch/Elasticsearch** (docker-compose service).
  - [x] Define index mapping for fields: title, abstract, authors, year, venue, doi, concepts/keywords, source, license, citations, fetched_at.
  - [x] Build indexer job to push from Postgres → Search index (idempotent; upsert by internal paper id).
  - [x] Implement analyzers (English, keyword) + fields for sorting (date, citations).
  - [x] Smoke tests: indexing, search latency < 200ms for top-k 20 on dev data (run `make search-up && make reindex && make bench`).

- [ ] **Query Model**
  - [x] Define `QuerySpec` (keywords, authors, year range, sources, license filter, max_results).
  - [x] Implement **author query** pathway for at least one connector (OpenAlex recommended).
  - [x] **Citation chaining (MVP)**:
        - [x] For a seed DOI: resolve references/citations via OpenAlex (metadata only).
        - [x] Enqueue discovered DOIs into ingestion (respect dedup + license) via CLI `hydrate-citations`.

- [x] **Scheduler & Job Orchestration (MVP)**
  - [x] Introduce a lightweight job runner (sweep-daemon) with a `sweeps.yaml` to define periodic topics.
  - [x] Jobs (CLI commands):
         - [x] `ingestion.cli run` (connector sweep)
         - [x] `ingestion.cli hydrate-citations` (citation chain)
         - [x] `ingestion.cli reindex` (reindex search)
  - [x] Observability: basic run logs + counters (ingested, deduped, skipped, license-blocked, errors).

- [x] **API Surface (Search)**
  - [x] `/search` (GET): forwards to search index (filters: keyword, author, year, license, source; sort by recency/citations).
  - [x] `/paper/{id}` (GET): returns DB metadata + PDF ref if stored.
  - [x] OpenAPI docs for the above.

- [x] **Compliance & Safety**
  - [x] License policy doc v0.2 (which licenses allow PDF storage vs metadata-only).
  - [x] Enforce storage rules (block/metadata-only if license disallows; applied in ingestion + API no-serve).
  - [x] Unit tests for license enforcement and “no-serve” behavior for restricted PDFs.

- [x] **Developer Experience**
  - [ ] `Makefile` targets:
        - [x] `make up` (db, search)
        - [x] `make sweep source=openalex q="large language models"`
        - [x] `make reindex`
        - [x] `make api`
        - [x] Update `README.md` with connector how-to and search examples.
        - [x] `sweep-file`/`sweep-daemon` commands to run YAML-defined sweeps.
  - [x] Seed sample commands/scripts for common flows.

---

## ✅ Acceptance Criteria

- [x] Two new sources integrated and proven via recorded tests and live smoke runs.
- [x] Search index returns <200ms p95 on dev corpus for top-k queries and supports:
      - [x] keyword search,
      - [x] author filter,
      - [x] year range filter,
      - [x] license filter,
      - [x] source filter,
      - [x] sort by recency or citation_count.
- [x] Citation chaining (depth=1) ingests at least 20 additional papers for a seed DOI without duplicates.
      (Validated via deterministic offline neighbors path; live mode implemented with robust fallbacks.)
- [x] License rules enforced: PDFs stored only when permitted; restricted ones are metadata-only.
- [x] API `/search` and `/paper/{id}` implemented with OpenAPI docs and covered by tests.
- [x] `make` targets run end-to-end on a clean machine (incl. dockerized services).

---

## 🔬 Test Plan (Representative)

- [ ] **Connector conformance:** each implements interface, returns normalized metadata, sets `license`, emits stable ids.
  - [x] Recorded for OpenAlex and Semantic Scholar; DOAJ optional
- [ ] **Dedup:** rerun a sweep; confirm no new rows for same results (by DOI or `(source, external_id)`).
- [ ] **Index mapping:** title/abstract analyzed; author keyword field exact-matchable; year sortable; license filterable.
- [ ] **Query correctness:** targeted queries return expected papers (golden set fixture).
- [ ] **Citation chain:** seed DOI yields correct neighbors (spot-check 5 with provider via `RUN_LIVE=1`).
- [ ] **Compliance:** attempt to ingest a restricted-license PDF → stored as metadata-only; API does not expose a PDF link.
  - [x] API `/paper/{id}` test validates no-serve behavior

---

## 📌 Notes & Constraints

- Prefer OpenAlex for citation/author graph; fall back gracefully when DOIs are missing.
- Keep connectors stateless; persist only via ingestion layer.
- Avoid over-indexing PDFs in Phase-2; full parsing/summarization is Phase-3.
- Telemetry now saves time later: record per-connector latency, hit counts, error rates.

---

## 🌱 Stretch (If Time Allows)

- [ ] Simple relevance scoring blend (BM25 + recency boost).
- [ ] Concept/keyword expansion from OpenAlex concepts.
- [ ] Basic admin dashboard (counts by source, errors, last sweep).
