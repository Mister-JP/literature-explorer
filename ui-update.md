# ui-e2e-tests.md — Automated UI Testing Plan

**Purpose**  
Automate verification of the literature UI with deterministic, repeatable tests that catch regressions early and produce screenshots/traces for fast debugging.

This plan specifies **what must exist** and **how we measure done**. Engineers choose the exact libraries/config (Playwright recommended, but not required).

---

## 1) Objectives (What success looks like)

- **Functional E2E** for the core flows (search → browse → details → star → export) on seeded data.
- **Visual snapshots** for the search page (catch accidental UI shifts).
- **Zero-results detection** with alerts (so “is it broken?” is measurable).
- **Artifacts on failure** (screenshots, video, trace) attached to CI runs.
- **Synthetic monitor** (nightly) against deployed env with a short, deterministic script.

---

## 2) Scope (What we will test)

**In-scope user journeys:**
1. Search with seeded query → non-zero results → details panel opens → sections render or empty message appears.
2. Zero-result query → empty state shows suggestions → “Report this search” logs an event.
3. Filters (thread, year range, license, source, `has_summary`) affect results and **URL syncs**.
4. Star an item, then export **current filter** and **starred** to CSV/JSONL.
5. Error handling: if `/paper/{id}` fails, UI shows “Failed to load sections.” and logs an `api_error`.

**Out of scope (for now):**
- Cross-browser matrix (Chrome only is fine).
- Deep a11y audits (basic axe check is enough).
- Full perf profiling (we’ll track latency pills + Lighthouse smoke).

---

## 3) Test Data & Determinism

- Tests must **not** hit live external APIs.  
- Use `make seed-demo-ui` (or equivalent) to preload a small, **known** corpus:
  - 3–5 papers for “transformer/LLM” (positive path).
  - 1 **deliberate zero** query (e.g., `thisshouldyieldzero`).
  - At least one item with parsed sections and one without.
- If seeds change, update the fixtures and baselines in the same PR.

---

## 4) Environments & Config

- Default local base URL: `http://localhost:8000` (override via `BASE_URL`).
- Headless runs in CI; engineers may run headed locally.
- Record artifacts **on failure** in local and CI runs.

**Required Make targets**
```bash
make e2e       # local run, opens HTML report if available
make e2e-ci    # CI mode, writes artifacts to artifacts/ui-e2e/
````

---

## 5) Must-Have Coverage (Test Stories & AC)

### T-01 Search renders count/latency/sort (Happy Path)

**AC**

* [x] Enter seeded query → header shows **result count**, **latency (ms)**, **sort**.
* [x] At least one row visible; no console errors.
* [x] Full-page screenshot saved.

**Artifacts:** screenshot on failure; trace/video optional.

- Completed 2025-08-10 by gpt-5-agent. Local run green; screenshot at `artifacts/ui-e2e/t01-search-happy.png`.

---

### T-02 Zero-result empty state + “Report this search”

**AC**

* [x] Enter deliberate zero query → empty state with 3 suggestions.
* [x] Clicking “Report this search” triggers a telemetry call (assert by API log or test stub).
* [x] Returning to a valid query clears empty state.

**Artifacts:** screenshot + network log on failure.

- Completed 2025-08-10 by gpt-5-agent. Local run green; verified POST `/ui/report` returns 200 and empty state clears on valid query.

---

### T-03 Details panel loads sections (and fails gracefully)

**AC**

* [x] Clicking “Details” opens panel; shows either parsed sections or “No parsed sections available.”
* [x] If the details API is forced to fail (mock/flag), UI shows a friendly failure message and logs `api_error`.

**Artifacts:** trace on failure.

- Completed 2025-08-10 by gpt-5-agent. Local run green; screenshots at `artifacts/ui-e2e/t03-details-success.png` and `t03-details-failure.png`.

---

### T-04 Filters + URL sync

**AC**

* [x] Set `thread` + year range + license + source + `has_summary`.
* [x] Results update; `location.search` reflects those filters.
* [x] Hard refresh preserves view; copying the URL reproduces state.

**Artifacts:** screenshot of filtered view baseline for visual diff.

- Completed 2025-08-10 by gpt-5-agent. Local run green; screenshot at `artifacts/ui-e2e/t04-filters.png`.

---

### T-05 Star + Export (filtered & starred)

**AC**

* [ ] Toggling star changes icon without page reload.
* [ ] Export current filter as CSV and JSONL returns 200 and non-empty content with expected fields.
* [ ] Export starred returns only the starred rows.

**Artifacts:** downloaded fixture checked (size/headers), or stubbed response validated.

---

### T-06 Visual baseline for Search page

**AC**

* [ ] Establish a single baseline snapshot of `/ui/search?q=<seed>`.
* [ ] Subsequent test runs diff against baseline; material changes require approved snapshot update.

**Artifacts:** visual diff images on failure.

---

### T-07 Synthetic monitor (deployed env)

**AC**

* [ ] Minimal script runs seeded positive and zero queries, asserts nonzero and zero respectively, and measures latency.
* [ ] If assertions fail or latency exceeds threshold, post an alert (webhook/log) and attach a screenshot.

**Schedule:** nightly (and manual trigger).

---

## 6) Telemetry Cross-Checks

* For T-01: assert a `search_results` event with `result_count > 0`.
* For T-02: assert a `search_zero_results` event (or `user_reported_zero` on click).
* Logging failure **must not** fail the test unless core functionality is broken.

---

## 7) Accessibility & Performance Smoke

* Run **Lighthouse** on `/ui/search?q=<seed>`; store score trend (no hard gate initially).
* Run **axe** to fail on **critical** issues only (missing labels, focus traps).

---

## 8) CI Integration

* Run all Must-Have tests on PRs.
* Upload artifacts (screenshots, video, trace) to CI.
* Post a brief run summary in the PR (pass/fail, counts).
* Nightly workflow runs synthetic monitor against the deployed URL (configurable).

---

## 9) Flake Policy

* Any flaky test must be quarantined within 24h:

  * Mark as `@flaky` (or skip with tracking issue).
  * Add a stabilization ticket with owner/ETA.
* No silently retried tests without surfacing flake counts.

---

## 10) Ownership & Workflow

* Tests live under `/ui-tests` (or agreed path).
* Code owners: UI team (functional), Platform (CI wiring), Data (seeds).
* Each test story tracked as its own PR:

  * Update seeds/fixtures and baselines in the same PR.
  * Include “How to reproduce locally” snippet in the PR description.

---

## 11) Definition of Done (project level)

* [ ] T-01 … T-07 implemented and green locally and in CI.
* [ ] Artifacts reliably attach to CI runs.
* [ ] Seeds make the suite deterministic; no calls to live providers.
* [ ] Nightly synthetic monitor alerts on zero-result spikes or latency breaches.
* [ ] A short **Runbook** exists: *“Debugging a failed UI E2E”* (open HTML report → inspect trace → reproduce with `BASE_URL`).

---

## 12) Suggested Layout (non-prescriptive)

```
/ui-tests
  /e2e
    search.spec.ts
    zero-results.spec.ts
    details.spec.ts
    filters.spec.ts
    star-export.spec.ts
  /fixtures
    seeds.json
  /snapshots
    search-page.spec.ts-snapshots/
  playwright.config.ts   # or cypress.config.ts
/artifacts/ui-e2e/       # CI outputs
```

---

## 13) Urgency

We routinely hit “0 results” and don’t know why. Automated, seeded E2E + visual checks turn that into **fast, observable failures** with screenshots and traces — not guesswork.
**Ship this test suite before expanding the UI surface area.**

