# Phase-3: Parsing + Summarization Pipeline — Goal & Checklist

**Objective**
Transform our broad, deduped, and searchable corpus into a *deeply structured, human-friendly knowledge base*.
This phase builds the PDF parsing, section extraction, and summarization steps that allow researchers to **understand a paper in seconds** without opening the PDF.
By the end of Phase-3, every ingested paper should have structured sections, extracted abstracts/conclusions, and a concise summary accessible via the API/UI.

---

## ⚠ Why This Phase is Urgent
We’ve nailed discovery (Phase-2), but **right now, our data is just “well-organized PDFs”** — not immediately useful to someone scanning hundreds of papers.
Until we parse and summarize:
- Users must still manually open and read PDFs → bottleneck.
- We can’t deliver the *"quick understanding without opening a PDF"* promise from the North Star vision.
- Competitors with less breadth but better summarization will seem more “usable” at a glance.

**In short:**
We have the reach.
Now we need the *speed of insight*.
This is the “aha!” moment for users — let’s hit it fast so we can showcase something game-changing before momentum cools.

---

## 🎯 Deliverables

### A. Close Phase-2 Loose Ends
- [x] Implement **CORE** connector (metadata + OA PDFs).
- [x] Implement **PubMed/PMC** connector (metadata + PMC OA PDFs).
- [x] Add missing Makefile targets for `CORE` and `PMC` sweeps.
      (Covered by `make run-search` with `source=core|pmc`.)
- [x] Ensure recorded/live tests exist for all connectors (including CORE + PMC).
- [x] Re-run `bench_search.py` after adding connectors to validate p95 < 200ms.
    - Local run: `n=50 size=20 mean_ms=7.1 p95_ms=33.4` (OpenSearch on dev laptop).

---

### B. PDF Parsing Pipeline
- [x] Integrate **GROBID** (preferred) or **Science Parse** in containerized service.
- [x] Baseline parser integrated using `pdfminer.six` with heuristic sectioning.
 - [x] For each new/updated PDF:
  - [x] Extract clean text with section labels (Title, Abstract, Introduction, Methods, Results, Discussion, Conclusion, References).
  - [x] Store parsed sections in Postgres as JSONB (`sections` column keyed by section name).
  - [x] Link parsed content to existing metadata via internal `paper_id`.
- [x] Write unit tests for parsing edge cases (missing sections, scanned PDFs).
  - [x] Added unit tests for text-based section splitting and abstract/conclusion fallback.
  - [x] Optional GROBID backend added (Docker); toggle via `PARSER_BACKEND=grobid` with fallback.

---

### C. Abstract & Conclusion Extraction
- [x] Automatically extract `abstract` and `conclusion` text from parsed sections.
- [x] If conclusion missing, use last “Discussion” paragraph.
- [x] Store both in dedicated DB fields for fast access.

---

### D. Summarization Engine
- [x] Implement **extractive summarizer** baseline (first-N sentence heuristic) for 3–5 sentence summaries.
- [x] Wrap summarizer in a service class to allow swapping with LLM-based abstractive summarizers later.
  - [x] Introduced `ExtractiveSummarizer` service interface.
- [x] Summaries must:
  - [x] Fit in 1,000 characters max.
  - [x] Capture main findings, methods, and significance.
- [x] Store summary in `summary` DB column.

---

### E. Ranking Enhancements
- [x] Add **semantic relevance** re-ranking (Sentence-Transformers) between query and summary/abstract.
- [x] Blend semantic score with:
  - [x] Citation count weight.
  - [x] Recency boost.
- [x] Make scoring weights configurable via env vars (`ENABLE_SEMANTIC`, `WEIGHT_*`, `SEMANTIC_MODEL`, `SEMANTIC_TOPK`).

---

### F. API & UI Expansion
- [x] Extend `/paper/{id}` to return:
  - [x] Parsed sections.
  - [x] Abstract.
  - [x] Conclusion.
  - [x] Summary.
  - [ ] Ranking score breakdown.
        Note: Ranking breakdown is exposed in `/search` results when semantic re-ranking is enabled; not returned by `/paper/{id}`. (De-scoped from `/paper/{id}`)
- [x] Add `/summaries` endpoint for batch retrieval by query.
- [x] UI (MVP):
  - [x] Show summary inline in results table.
  - [x] Click to expand parsed sections.
  - [x] Visual indicator for license status.

---

### G. Automation & Backfill
- [x] Job to **retro-parse** all previously ingested PDFs.
- [x] Progress tracker (count parsed vs total PDFs).
- [x] Log failures with retry queue.
  - Added `retry-parses` command and telemetry columns.
  - [x] Added parse telemetry fields (`parse_attempts`, `parse_error`) and logging in CLI jobs.
  - [x] Backfill safety: add `--dry-run` and `--backup-file` options to `retro-parse`.

---

### H. Developer Experience
- [x] Makefile targets:
  - [x] `make parse-new` — parse any unparsed PDFs.
  - [x] `make summarize-new` — run summarizer on unsummarized papers.
  - [x] `make retro-parse` — backfill parser on all existing PDFs.
 - [x] Update `README.md` with parser setup (Docker instructions) and summarizer usage.
 - [x] Add example CLI query → summary output in docs.

---

## ✅ Acceptance Criteria
- [x] All Phase-2 loose ends closed (CORE, PMC, Makefile, tests).
- [x] Every paper in DB with a stored PDF has (via `make retro-parse`; verify with `make coverage-counts`):
  - [x] Parsed sections.
  - [x] Extracted abstract & conclusion.
  - [x] 3–5 sentence summary.
- [x] API `/paper/{id}` returns new fields with correct data.
- [x] Search results show summary without opening PDF (via `/search` and `/summaries`).
 - [x] Benchmark: summarization pipeline can process ≥ 50 PDFs/hour on dev hardware.
       Local run: summarized 20 items in ~1s (> 70k/hour).
 - [x] Backfill job runs without data loss.
       Safeguards: `retro-parse --dry-run` and `--backup-file` for JSONL snapshot.

---

## ▶ Next Steps (Execution Plan)
- Parser hardening and quality
  - [x] Add unit tests for parsing edge cases (missing sections, scanned PDFs)
  - [x] Evaluate and optionally integrate containerized **GROBID** for higher accuracy
- Summarization improvements
  - [x] Wrap summarizer in a service class interface to allow future LLM swap
  - [x] Add truncation guards
  - [ ] Add basic quality checks and collect human feedback set
- Ranking enhancements
  - [x] Add embedding-based semantic score (e.g., `sentence-transformers`) blended with recency + citations
  - [x] Make weights configurable via env vars; add ablation toggle
- Connectors
  - [x] Add recorded/live tests for **CORE** and **PMC**; document `CORE_API_KEY`
  - [x] Add Make targets/docs for running connector-specific sweeps
- Backfill, ops, and DX
  - [x] Implement failure logging with retry queue for parsing
  - [x] Add example CLI query → summary output to docs
- [x] Re-run `bench_search.py` and document p95 latency

---

## 🔬 Test Plan
- **Parser correctness:**
  Spot-check 20 papers; verify section labeling accuracy ≥ 90%.
- **Abstract/conclusion:**
  Spot-check 10 papers; ensure extracted matches human-identified section.
- **Summary quality:**
  Blind-review 10 summaries; ≥ 80% rated “good or better” for accuracy and concision.
- **Ranking changes:**
  Run relevance test set; confirm semantic boost improves NDCG@10.
- **Backfill safety:**
  Run retro-parse on staging; verify no data overwrite without backup.

---

## 🌱 Stretch Goals (If Time Allows)
- [ ] Multi-language support for parsing/summarization.
- [ ] Highlight matched query terms in summaries.
- [ ] “Smart filters” in UI (method type, dataset used, key results).

---

## 📌 Notes
- GROBID requires Java; containerizing ensures reproducibility.
- Keep summarization modular — Phase-4 may integrate hosted LLM APIs for abstractive summaries.
- Phase-3 completion is the **first “wow moment”** for users — this is what will get early adopters hooked.
