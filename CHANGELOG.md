# Changelog

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


