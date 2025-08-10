# Phase-2: Discovery Expansion & Search Index — Goal & Checklist

**Objective**  
Expand beyond arXiv with a plug-in connector pattern, introduce a real search index for fast retrieval, and support richer queries (keyword, author, and first pass at citation chaining). The outcome is a broader, faster corpus that remains legally safe and deduped.

---

## 🎯 Deliverables

### Status snapshot (in repo)

- Connector base plus arXiv, OpenAlex, Semantic Scholar, and DOAJ implemented; ingestion → DB working with dedup and license gate; OpenSearch + indexer + API live. Author/year filters and license filter validated; citations sort validated; citation chaining MVP and sweep-daemon added.
- Conformance tests recorded for OpenAlex and Semantic Scholar (via VCR). DOAJ optional (API variance); can be enabled with `INCLUDE_DOAJ=1` when recording.
- License policy doc added and enforced in ingestion + API.
- p95 latency on dev corpus (n=50, size=20) measured locally: ~6.5ms p95 (mean ~13.7ms). Target <200ms met.

- [ ] **Connector Framework (Production-Ready)**
  - [x] Finalize `BaseConnector` interface (type hints + docstrings) with methods:
        `search(query: QuerySpec) -> Iterable[PaperMetadata]`, `fetch_pdf(item: PaperMetadata) -> Optional[PDFRef]`.
  - [ ] Shared utilities:
        - [x] Backoff/retry (downloader)
        - [x] Per-source rate limits utility
        - [x] Telemetry hooks
        - [x] License extractor/normalizer
  - [ ] Connector conformance tests (pytest) with a small cassette-based suite (e.g., `vcrpy`) and recorded fixtures.
    - [x] OpenAlex and Semantic Scholar recorded
    - [ ] DOAJ recorded (optional; enable via `INCLUDE_DOAJ=1`)

- [ ] **New Connectors (at least two of the following)**
  - [x] **OpenAlex**: keyword + author queries; pull DOI, concepts, citations, license where available. (initial implementation; refine author filter, surface OA PDF URL)
  - [x] **Semantic Scholar** (open endpoints): metadata enrichment (citations, influential citations).
  - [x] **DOAJ** (Directory of Open Access Journals): metadata + OA status.
  - [ ] **CORE**: OA metadata and PDF links (respecting license).
  - [ ] **PubMed/PMC**: E-utilities for metadata; PMC OA subset for PDFs and license tags.
  - [ ] Each connector:
        - [x] Honors legal/licensing fields and stores a normalized `license` string (normalization enforced in ingestion layer).
        - [x] Emits `(source, external_id)` and DOI for dedup.
        - [x] Returns consistent `PaperMetadata` with `sections` empty (parsing is Phase-3).

- [ ] **Search Index**
  - [x] Stand up **OpenSearch/Elasticsearch** (docker-compose service).
  - [x] Define index mapping for fields: title, abstract, authors, year, venue, doi, concepts/keywords, source, license, citations, fetched_at.
  - [x] Build indexer job to push from Postgres → Search index (idempotent; upsert by internal paper id).
  - [x] Implement analyzers (English, keyword) + fields for sorting (date, citations).
  - [ ] Smoke tests: indexing, search latency < 200ms for top-k 20 on dev data.

- [ ] **Query Model**
  - [x] Define `QuerySpec` (keywords, authors, year range, sources, license filter, max_results).
  - [x] Implement **author query** pathway for at least one connector (OpenAlex recommended).
  - [ ] **Citation chaining (MVP)**:
        - [x] For a seed DOI: resolve references/citations via OpenAlex/Semantic Scholar (metadata only).
        - [x] Enqueue discovered DOIs into ingestion (respect dedup + license).

- [ ] **Scheduler & Job Orchestration (MVP)**
  - [x] Introduce a lightweight job runner (sweep-daemon) with a `sweeps.yaml` to define periodic topics.
  - [x] Jobs:
         - [x] `run_connector_sweep(queryspec, source)`
         - [x] `hydrate_citation_chain(seed_doi, depth=1)`
         - [x] `reindex_search(batch_size=N)`
  - [x] Observability: basic run logs + counters (ingested, deduped, skipped, license-blocked, errors).

- [ ] **API Surface (Search)**
  - [x] `/search` (GET): forwards to search index (filters: keyword, author, year, license, source; sort by recency/citations).
  - [x] `/paper/{id}` (GET): returns DB metadata + PDF ref if stored.
  - [x] OpenAPI docs for the above.

- [ ] **Compliance & Safety**
  - [x] License policy doc v0.2 (which licenses allow PDF storage vs metadata-only).
  - [x] Enforce storage rules (block/metadata-only if license disallows; applied in ingestion + API no-serve).
  - [x] Unit tests for license enforcement and “no-serve” behavior for restricted PDFs.

- [ ] **Developer Experience**
  - [ ] `Makefile` targets:
        - [x] `make up` (db, search, worker)
      - [x] `make sweep source=openalex q="large language models"`
        - [x] `make reindex`
      - [x] Update `README.md` with connector how-to and search examples.
      - [x] `sweep-file` command to run YAML-defined sweeps.
  - [ ] Seed sample commands/scripts for common flows.

---

## ✅ Acceptance Criteria

- [ ] Two new sources integrated and proven via recorded tests and live smoke runs.
- [ ] Search index returns <200ms p95 on dev corpus for top-k queries and supports:
      - [x] keyword search,
      - [x] author filter,
      - [x] year range filter,
      - [x] license filter,
      - [x] source filter,
      - [x] sort by recency or citation_count.
- [ ] Citation chaining (depth=1) ingests at least 20 additional papers for a seed DOI without duplicates.
- [ ] License rules enforced: PDFs stored only when permitted; restricted ones are metadata-only.
- [ ] API `/search` and `/paper/{id}` live with OpenAPI docs and pass CI tests.
- [ ] `make` targets run end-to-end on a clean machine (incl. dockerized services).

---

## 🔬 Test Plan (Representative)

- [ ] **Connector conformance:** each implements interface, returns normalized metadata, sets `license`, emits stable ids.
  - [x] Recorded for OpenAlex and Semantic Scholar; DOAJ optional
- [ ] **Dedup:** rerun a sweep; confirm no new rows for same results (by DOI or `(source, external_id)`).
- [ ] **Index mapping:** title/abstract analyzed; author keyword field exact-matchable; year sortable; license filterable.
- [ ] **Query correctness:** targeted queries return expected papers (golden set fixture).
- [ ] **Citation chain:** seed DOI yields correct neighbors (spot-check 5 with provider).
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
