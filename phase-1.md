# Phase-1: Backend Foundations — Goal & Checklist

**Objective:**  
Establish a working ingestion pipeline that can connect to at least one open-access source (e.g., arXiv), fetch metadata + full-text PDFs (where licensing allows), and persist them in storage with a consistent schema.  
By the end of Phase-1, we should have a minimal but functioning backend capable of running targeted searches and storing results in a way that future phases can build upon.

---

## 🎯 Deliverables
- [x] **Codebase Bootstrapped**
  - [x] Create project repository (this repo).
  - [x] Set up Python environment with dependency management (Poetry via `pyproject.toml`; optional `requirements.txt`).
  - [ ] Initialize version control branch protection rules (repo exists; branch protection TBD).
  - [x] Configure CI pipeline for automated linting & tests (GitHub Actions present).

- [x] **Database & Storage Setup**
  - [x] Provision **PostgreSQL** (local/dev via `docker-compose.yml`).
  - [x] Define initial metadata schema (`papers` with `id`, `source`, `external_id`, `doi`, `title`, `authors` JSON, `abstract`, `license`, `pdf_path`, `fetched_at`).
  - [x] Configure blob storage (local filesystem under `data/pdfs`).
  - [x] Create a metadata–PDF mapping mechanism (store `pdf_path` in DB).

- [x] **Connector Architecture**
  - [x] Define a base connector interface (simplified to `search(query, max_results)` returning `PaperMetadata`).
  - [x] Implement **arXiv connector**:
    - [x] Support keyword search.
    - [x] Fetch metadata + PDF link.
    - [x] Store metadata in DB.
    - [x] Download PDF to blob storage.
  - [x] Implement error handling, retry logic, and rate limiting (download retries + configurable sleep).

- [x] **Deduplication Logic**
  - [x] Detect duplicates by DOI (preferred), `(source, external_id)`, or metadata hash.
  - [x] Skip ingestion if already present.

- [x] **Basic Command-Line Trigger**
  - [x] CLI command to run a search query against arXiv.
  - [x] Output: number of results stored, skipped, and errors (fetched count can be inferred).

- [x] **Developer Documentation**
  - [x] `README.md` with setup instructions (env vars, DB setup, running a search).
  - [x] Connector interface documentation (how to add a new source).
  - [x] Licensing & compliance note (store license metadata if available).

---

## ✅ Phase-1 Completion Criteria
- [x] A new developer can clone the repo, install deps, and run a search to ingest data. For example:
  - Poetry:
    ```bash
    poetry install --no-root
    PYTHONPATH=src poetry run python -m ingestion.cli --query "X" --max-results 5
    ```
  - pip (module path via editable install):
    ```bash
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    pip install -e .
    python -m ingestion.cli --query "X" --max-results 5
    ```
  - Makefile:
    ```bash
    make run-search query="X" max=5
    ```
  - [x] Metadata stored in DB.
  - [x] PDFs stored in blob storage.
- [x] No duplicates are stored for repeated queries.
- [ ] All code passes linting & basic tests in CI (CI configured; first green run pending).
- [x] Minimal docs exist for setup & connector extension.

---

## 📌 Notes
- For MVP, focus only on **arXiv** integration to avoid scope creep.
- Keep **connector logic isolated** so Phase-2 can simply add more connectors without touching core ingestion code.
- License metadata capture is **critical** for future legal filtering — do not skip.
 - Makefile target `run-search` is aligned and tested.

