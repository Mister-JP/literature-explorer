# Changelog

## 2025-08-10
- Add Playwright E2E scaffolding and T-01 test (`ui-tests/e2e/test_t01_search_happy_path.py`).
- Add Make targets `e2e`/`e2e-ci`; update `requirements.txt` for playwright, pytest-playwright, ruff, black.
- Adjust `ui_search.html` header rendering to always include result metadata container for tests.
- Implement T-02 zero-results test and fix async JSON parsing in `/ui/report` and `/ui/telemetry`.
- Add T-03 details test (+ artifacts), T-04 filters URL sync (+ artifact), T-05 star/export (+ CSV artifacts).
- Add T-06 visual baseline with Pillow; baseline created.
- Add T-07 synthetic monitor E2E wrapper.

## 0.2.0 - Phase-2

- Connector framework finalized; added OpenAlex, Semantic Scholar, DOAJ
- Ingestion pipeline with deduplication and license normalization/enforcement
- Search index (OpenSearch) + indexer job; API `/search` and `/paper/{id}`
- Query filters: author, year range, license, source; sort by recency/citations
- Citation chaining MVP and sweep-daemon for periodic sweeps
- Per-source rate limiter and HTTP JSON helper
- Tests: license policy, API behavior, search query construction, live conformance (gated), citation chain
- Docs: README updates, license policy doc, Phase-2 plan updated
- Benchmark: p95 < 200ms achieved on dev corpus
## Unreleased

- Docs: mark UI filters status complete in engineering spec; no functional changes.
