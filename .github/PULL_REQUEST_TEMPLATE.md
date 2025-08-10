## Summary

Describe the changes in this PR and the motivation.

## Phase & Scope

- [ ] Phase-2
- [ ] Other (specify)

## Checklist

- [ ] Tests added/updated as needed
- [ ] `make test` green locally
- [ ] If touching ingestion or connectors, recorded tests either gated behind `RUN_LIVE=1` or with cassettes
- [ ] License policy respected (`license_permits_pdf_storage`), no restricted PDFs served via API
- [ ] OpenSearch index mapping unaffected or updated via `reindex`
- [ ] Docs updated (`README.md`, `phase-2.md`, or `docs/`)

## Validation

- [ ] Ingested sample: `python -m ingestion.cli run --query "..." --source ...`
- [ ] Reindexed: `python -m ingestion.cli reindex`
- [ ] API smoke: `/search` and `/paper/{id}`
- [ ] Optional: `make bench` p95 under target

## Screenshots / Logs (optional)


