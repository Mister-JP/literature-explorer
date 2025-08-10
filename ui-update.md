# How to Work This File

Read this file before starting any UI work. Follow the execution loop, then work the checklist. Update this file as items are completed.

## Core Principles

- Keep changes small, focused, and reversible. Prefer small PRs with a clean, linear commit history.
- Validate locally before pushing: lint, format, tests, and a manual UI smoke check.
- Favor clarity over cleverness; optimize for readability and maintainability.
- Instrument features: add telemetry and basic operational visibility alongside UI changes.
- Respect privacy: log query hashes (not raw text) and avoid PII.
- Update the source of truth: this file and relevant docs must reflect reality as you ship.

## Daily Loop

1) Sync Plan
- Read the checklist below and pick the next highest-impact item.
- Fill in Owner and Target date for the item you’re taking.
- Break work into a minimal vertical slice that can be validated end-to-end.

2) Implement
- Create a feature branch and implement the smallest coherent increment.
- Add telemetry and operational hooks while building the UI.

3) Validate Locally
- Run through local checks and a quick manual smoke of the UI.

```bash
# Install and prepare environment (first time)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Start backing services as needed
make search-up || true
make db-up || true

# Seed demo data and index
make seed-demo-ui
make reindex

# Run API + UI locally
make api   # visit http://localhost:8000/ui/search?q=transformer

# Quality gates
make lint && make format && make test
```

4) Update Docs
- Check off the item(s) you completed in this file.
- Update `README.md` or linked docs if behavior or usage has changed.

5) Open PR
- Keep PRs small and self-contained. Link to the item(s) checked here.
- Include evidence of local validation and any relevant screenshots.
- Ensure CI is green (lint, format, tests) before requesting review.

## Quick Reference

```bash
# One-time setup (Poetry optional alternative exists in Makefile)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Services
make search-up     # start OpenSearch
make db-up         # start PostgreSQL (optional; SQLite by default)
make up            # start DB+Search together
make down          # stop DB+Search

# Data, indexing, and API/UI
make seed-demo-ui
make reindex
make api           # FastAPI at http://localhost:8000

# CLI examples
python -m ingestion.cli run --query "transformer" --max-results 3 --source arxiv
make run-search query="transformer" max=3

# Quality + tooling
make lint
make format
make test
make bench         # benchmark search
```

## Definition of Done (per item)

- [ ] Owner and Target date are set in this file for the item.
- [ ] UI behavior implemented and manually validated (normal, loading, and zero-result states).
- [ ] Telemetry/events added (and do not break the UI on failure).
- [ ] Accessibility sanity pass (labels, focus order, keyboard where applicable).
- [ ] Performance sanity: visible latency regression avoided for the feature surface.
- [ ] Tests updated or added; `make lint`, `make format`, and `make test` pass locally.
- [ ] Documentation updated (this file and, if needed, `README.md`).
- [ ] PR merged with a concise, clean commit history.

---

# UI Improvement & Feedback Requirements

**Purpose:**
Enhance the literature search UI to provide a smoother, more transparent user experience and add a feedback/telemetry layer so both users and engineers know when the system is failing or underperforming.

---

## 1. User Experience Improvements

**Goal:** Make the search and browsing experience feel responsive, trustworthy, and easy to navigate.

**Requirements:**
- Show **result count**, **latency**, and **current sort order** prominently after every search.
- When **0 results** are returned:
  - Display a clear empty state with suggestions for refining the search.
  - Provide a one-click “Report this search” action.
- While results are loading:
  - Show loading indicators or skeleton rows to communicate progress.
- Under each title:
  - Display key provenance info (e.g., source, DOI/arXiv/PMC links if available).
- Summaries:
  - Truncate long summaries with a “Show more” option to expand.
- Filters:
  - Allow quick filtering by thread, year range, venue, license, source, and `has_summary` status.
  - Keep filter state in the URL for shareable links.
- Actions:
  - Provide “Star” functionality for saving results.
  - Enable export of either the current filtered set or only starred results.
- Optional usability:
  - Add basic keyboard navigation for moving through results and toggling details/stars.

---

## 2. Feedback & Telemetry

**Goal:** Capture structured, privacy-safe feedback events from the UI so engineers can detect and diagnose problems (e.g., high zero-result rates, failing connectors, API errors) quickly.

**Requirements:**
- Client should log:
  - Search submission events (with query hash and filter context).
  - Search results events (result count, latency).
  - Zero-result events (with filter context).
  - API error events (endpoint, status, latency, short note).
  - Details loaded/failed, star toggled, export clicked.
- Telemetry must:
  - Include a session identifier and UI version tag.
  - Be stored server-side in a structured table for later analysis.
  - Be designed so logging failures never break the UI.
- Engineers must be able to:
  - Aggregate metrics (hourly) for zero-result rate, error rate, and latency.
  - Trigger alerts when thresholds are breached (e.g., zero-result rate > X% in Y minutes).
- All telemetry must respect privacy:
  - Log query **hashes**, not raw query text.
  - Avoid any personally identifiable information.

---

## 3. Operational Visibility

**Goal:** Make it easy for operators to monitor UI health and debug issues.

**Requirements:**
- Provide a simple debug overlay (toggleable) showing:
  - Last search payload.
  - Latency.
  - Result count.
  - Build/version ID.
- Add a basic synthetic monitor job:
  - Runs canned queries on a schedule.
  - Asserts that results are returned and latency is acceptable.
  - Reports failures via the same alerting channel as telemetry.

---

## 4. Definition of Done

**The UI changes are considered complete when:**
- Users can:
  - See result count, latency, and sort order after every search.
  - Understand and act when zero results are returned.
  - Easily filter, star, and export results without backend/code changes.
- Engineers can:
  - View telemetry data for any search session.
  - Detect and be alerted to systemic issues within minutes.
  - Run a synthetic monitor to confirm UI/API health.
- All changes are:
  - Documented in `README.md` or a dedicated UI guide.
  - Tested for basic functional correctness.

---

## 5. Deliverables Summary

- [x] Result header with count, latency, sort.
- [x] Empty state with suggestions and “Report” action.
- [x] Loading indicators for search and details.
- [x] Provenance info under titles.
Owner: JP
Target: 2025-08-10

Notes: Implemented provenance badges/links under titles in `src/ingestion/templates/ui_search.html`. Shows source badge and links for DOI, arXiv, and PMC when available. No backend changes required.
- [x] Truncated summaries with expansion.
- [x] Filter controls for key fields; URL sync.
- [x] Star & export features.
- [x] Client-side event logging for all key actions.
- [x] Backend storage and aggregation for telemetry.
- [x] Alerting for high error/zero-result rates.
- [x] Debug overlay for quick inspection.
- [x] Synthetic monitor for end-to-end health checks.

Owner: JP
Target: 2025-08-10

Notes: Implemented a lightweight telemetry helper and wired events in `src/ingestion/templates/ui_search.html` for `search_submit`, `search_results`, `zero_result`, `api_error` (details fetch), `details_loaded`/`details_failed`, `star_toggled`, and `export_clicked`. Events include `session_id`, `ui_version`, `ts_iso`, `url`, and privacy-preserving `query_hash`. Uses `navigator.sendBeacon` with fallback to `fetch` and never blocks or breaks UI on failure. Endpoint placeholder: `/ui/telemetry` (to be implemented in the backend item).
Follow-up: Added `/ui/telemetry` POST for ingest and `/ui/telemetry/metrics` GET for hourly aggregates (zero-result rate, error rate, avg latency). Data is stored in `ui_events`. Aggregation runs in-process and returns buckets for the last N hours.

Implementation details for alerting:
- Added `/ui/telemetry/alerts` in `src/ingestion/api.py` that evaluates windowed metrics and returns alert flags for zero-result and details error rates, with thresholds and minimum sample sizes configurable via query params.
- Optional webhook: set `ALERT_WEBHOOK_URL` env and call with `send=1` to POST an alert payload when active.

Debug overlay implementation:
- Toggle button added to `src/ingestion/templates/ui_search.html` (fixed bottom-right). Panel shows result count, latency, sort, build/version ID, and last search payload JSON; uses sessionStorage and current DOM meta to populate. Non-blocking and privacy-safe.
- Backend passes `build_version` to template via `src/ingestion/api.py` (`UI_BUILD_ID` env or app.version fallback).

Synthetic monitor implementation:
- Added `scripts/synthetic_monitor.py` which runs canned queries against the API `/search`, asserts non-zero results and latency under a configurable threshold, and reports failures via `ALERT_WEBHOOK_URL` (if set) or falls back to posting a `synthetic_failure` event to `/ui/telemetry`.
- Added `make monitor` target to run locally or in cron. Config via env or flags: `MONITOR_BASE_URL`, `MONITOR_QUERIES`, `MONITOR_MAX_LATENCY_MS`, `MONITOR_INTERVAL`.
