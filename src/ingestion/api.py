from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from opensearchpy import OpenSearch

from .config import Settings
from .db import Base, create_session_factory
from .models import Paper, UiEvent
from .utils import license_permits_pdf_storage


@asynccontextmanager
async def _lifespan(_: FastAPI):
    # Ensure DB schema exists on startup
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    with session_factory() as session:
        engine = session.get_bind()
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Literature Search API", version="0.2.0", lifespan=_lifespan)
templates = Jinja2Templates(directory="src/ingestion/templates")


def _get_client() -> OpenSearch:
    host = os.environ.get("SEARCH_HOST", "http://localhost:9200")
    return OpenSearch(hosts=[host])


INDEX_NAME = os.environ.get("SEARCH_INDEX", "papers")


@app.get("/paper/{paper_id}")
def get_paper(paper_id: int) -> dict[str, Any]:
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    with session_factory() as session:
        paper = session.get(Paper, paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        payload = {
            "id": paper.id,
            "source": paper.source,
            "external_id": paper.external_id,
            "doi": paper.doi,
            "title": paper.title,
            "authors": paper.authors.get("list", []) if paper.authors else [],
            "abstract": paper.abstract,
            "sections": paper.sections or {},
            "conclusion": paper.conclusion,
            "summary": paper.summary,
            "license": paper.license,
            "fetched_at": paper.fetched_at.isoformat() if paper.fetched_at else None,
        }
        # Enforce no-serve policy for restricted licenses
        if paper.pdf_path and license_permits_pdf_storage(paper.license):
            payload["pdf_path"] = paper.pdf_path
        else:
            payload["pdf_path"] = None
        return payload


@app.get("/search")
def search(
    q: str | None = Query(None, description="Keyword query"),
    author: str | None = Query(None, description="Author filter"),
    year_start: int | None = Query(None),
    year_end: int | None = Query(None),
    license: str | None = Query(None, alias="license"),
    source: str | None = Query(None),
    sort: str = Query("recency", description="recency|citations"),
    size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    client = _get_client()
    settings = Settings.from_env()

    must: list[dict[str, Any]] = []
    filter_q: list[dict[str, Any]] = []

    if q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "title^2",
                        "abstract",
                        "summary",
                    ],
                }
            }
        )
    if author:
        filter_q.append({"term": {"authors": author}})
    if year_start is not None or year_end is not None:
        range_body: dict[str, Any] = {}
        if year_start is not None:
            range_body["gte"] = year_start
        if year_end is not None:
            range_body["lte"] = year_end
        filter_q.append({"range": {"year": range_body}})
    if license:
        filter_q.append({"term": {"license": license}})
    if source:
        filter_q.append({"term": {"source": source}})

    sort_clause = [{"fetched_at": {"order": "desc"}}]
    if sort == "citations":
        sort_clause = [{"citation_count": {"order": "desc"}}]

    query = {"bool": {"must": must or {"match_all": {}}, "filter": filter_q}}

    res = client.search(
        index=INDEX_NAME, body={"query": query, "size": size * 2, "sort": sort_clause}
    )
    hits = [
        {
            "id": int(h.get("_id")) if str(h.get("_id")).isdigit() else h.get("_id"),
            "score": h.get("_score"),
            **h.get("_source", {}),
        }
        for h in res.get("hits", {}).get("hits", [])
    ]
    # Optional semantic re-ranking
    if settings.enable_semantic and q and hits:
        try:
            from sentence_transformers import SentenceTransformer, util  # type: ignore

            model = SentenceTransformer(settings.semantic_model)

            # Prepare texts to embed (prefer summary, then abstract, then title)
            def _text(item: dict[str, Any]) -> str:
                return item.get("summary") or item.get("abstract") or item.get("title") or ""

            topk = max(1, min(len(hits), settings.semantic_topk))
            subset = hits[:topk]
            corpus_texts = [_text(h) for h in subset]
            query_emb = model.encode([q], normalize_embeddings=True)[0]
            corpus_embs = model.encode(corpus_texts, normalize_embeddings=True)
            sims = util.cos_sim(query_emb, corpus_embs).tolist()[0]

            # Compute blended score: semantic + citations + recency
            def _safe(v: Any, default: float = 0.0) -> float:
                try:
                    return float(v or 0)
                except Exception:
                    return default

            def _recency_bonus(item: dict[str, Any]) -> float:
                # naive: newer year -> higher bonus
                y = _safe(item.get("year"))
                return y / 2100.0  # scale roughly into 0..1

            for i, item in enumerate(subset):
                semantic = float(sims[i])
                citations = _safe(item.get("citation_count"))
                blended = (
                    settings.weight_semantic * semantic
                    + settings.weight_citations * (citations**0.5)
                    + settings.weight_recency * _recency_bonus(item)
                )
                item["_blended_score"] = blended
                item["ranking_breakdown"] = {
                    "semantic": semantic,
                    "citations": citations,
                    "recency": _recency_bonus(item),
                    "weights": {
                        "semantic": settings.weight_semantic,
                        "citations": settings.weight_citations,
                        "recency": settings.weight_recency,
                    },
                }
            subset.sort(key=lambda x: x.get("_blended_score", 0.0), reverse=True)
            hits = subset[:size]
        except Exception:
            hits = hits[:size]
    else:
        hits = hits[:size]
    return {"total": res.get("hits", {}).get("total", {}).get("value", 0), "hits": hits}


@app.get("/ui/search", response_class=HTMLResponse)
def ui_search(
    request: Request,
    q: str | None = Query(None, description="Keyword query"),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("recency", description="recency|citations"),
    # Filters
    year_start: int | None = Query(None),
    year_end: int | None = Query(None),
    license: str | None = Query(None),
    source: str | None = Query(None),
    venue: str | None = Query(None),
    has_summary: int | None = Query(None, description="1 to require summary"),
) -> HTMLResponse:
    client = _get_client()
    must: list[dict[str, Any]] = []
    filter_q: list[dict[str, Any]] = []
    if q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": ["title^2", "abstract", "summary"],
                }
            }
        )
    # Filters
    if year_start is not None or year_end is not None:
        range_body: dict[str, Any] = {}
        if year_start is not None:
            range_body["gte"] = year_start
        if year_end is not None:
            range_body["lte"] = year_end
        filter_q.append({"range": {"year": range_body}})
    if license:
        filter_q.append({"term": {"license": license}})
    if source:
        filter_q.append({"term": {"source": source}})
    if venue:
        filter_q.append({"term": {"venue": venue}})
    if has_summary:
        filter_q.append({"exists": {"field": "summary"}})

    query = {"bool": {"must": must or {"match_all": {}}, "filter": filter_q}}

    sort_clause = [{"fetched_at": {"order": "desc"}}]
    if sort == "citations":
        sort_clause = [{"citation_count": {"order": "desc"}}]

    start_time = perf_counter()
    res = client.search(
        index=INDEX_NAME,
        body={"query": query, "size": size, "sort": sort_clause},
    )
    latency_ms = int((perf_counter() - start_time) * 1000)

    hits = [
        {
            "id": int(h.get("_id")) if str(h.get("_id")).isdigit() else h.get("_id"),
            **(h.get("_source", {}) or {}),
        }
        for h in res.get("hits", {}).get("hits", [])
    ][:size]
    total = res.get("hits", {}).get("total", {}).get("value", 0)

    # Render table with inline summary and expandable sections when available
    # Resolve build/version identifier for UI debug overlay
    build_version = os.environ.get("UI_BUILD_ID") or getattr(app, "version", "dev")

    return templates.TemplateResponse(
        "ui_search.html",
        {
            "request": request,
            "q": q or "",
            "items": hits,
            "total": total,
            "latency_ms": latency_ms,
            "sort": sort,
            "build_version": build_version,
            # reflect filters for URL sync/UI state
            "year_start": year_start,
            "year_end": year_end,
            "license": license or "",
            "source": source or "",
            "venue": venue or "",
            "has_summary": bool(has_summary),
        },
    )


@app.post("/ui/report")
async def ui_report(
    request: Request,
) -> JSONResponse:
    """Accept lightweight, privacy-safe UI feedback events.

    Expects JSON body like:
    {
      "session_id": "abc",
      "ui_version": "v1",
      "event_type": "report_search",
      "payload": {"query_hash": "...", "filters": {...}, "note": "optional"}
    }
    """
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event = UiEvent(
        session_id=str(body.get("session_id") or ""),
        ui_version=str(body.get("ui_version") or ""),
        event_type=str(body.get("event_type") or "report"),
        payload=body.get("payload") or {},
    )

    with session_factory() as session:
        session.add(event)
        session.commit()

    return JSONResponse({"ok": True})


@app.post("/ui/telemetry")
async def ui_telemetry(request: Request) -> JSONResponse:
    """Persist privacy-safe UI telemetry events.

    Expected JSON body (best-effort parsed):
    {
      "session_id": "...",
      "ui_version": "v1",
      "event_type": "search_results|zero_result|api_error|...",
      "ts_iso": "2025-08-10T12:34:56Z",  # optional
      "url": "/ui/search?...",            # optional
      "payload": { ... }                    # structured fields (no PII)
    }
    Logging failures should never break the UI, so this endpoint always returns {"ok": true}
    unless the request body is completely unreadable.
    """
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        # Return 200 with ok:false to avoid client disruption
        return JSONResponse({"ok": False})

    event = UiEvent(
        session_id=str(body.get("session_id") or ""),
        ui_version=str(body.get("ui_version") or ""),
        event_type=str(body.get("event_type") or "unknown"),
        payload=body.get("payload") or {},
    )

    try:
        with session_factory() as session:
            session.add(event)
            session.commit()
    except Exception:
        # Swallow errors to ensure UI is not impacted
        return JSONResponse({"ok": False})

    return JSONResponse({"ok": True})


@app.get("/ui/telemetry/metrics")
def ui_telemetry_metrics(hours: int = Query(24, ge=1, le=168)) -> dict[str, Any]:
    """Return hourly aggregates for key UI telemetry.

    - zero-result rate computed from search_results where payload.total == 0
    - avg latency_ms from search_results.payload.latency_ms
    - error rate computed from details requests: api_error vs (api_error + details_loaded)
    """
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(hours=hours)

    # Collect relevant events in window.
    with session_factory() as session:
        # Load minimal columns to Python and aggregate in-memory for simplicity and portability
        rows = (
            session.query(UiEvent.created_at, UiEvent.event_type, UiEvent.payload)
            .filter(UiEvent.created_at >= window_start)
            .filter(UiEvent.created_at <= window_end)
            .all()
        )

    def bucket_start(dt: datetime) -> datetime:
        return dt.replace(minute=0, second=0, microsecond=0)

    buckets: dict[datetime, dict[str, Any]] = {}

    for created_at, event_type, payload in rows:
        b = bucket_start(created_at)
        if b not in buckets:
            buckets[b] = {
                "searches": 0,
                "zero_searches": 0,
                "latency_sum": 0,
                "latency_count": 0,
                "details_requests": 0,  # details_loaded + api_error
                "details_errors": 0,  # api_error only
            }

        data = buckets[b]
        if event_type == "search_results":
            data["searches"] += 1
            try:
                total = int((payload or {}).get("total") or 0)
            except Exception:
                total = 0
            if total == 0:
                data["zero_searches"] += 1
            try:
                latency = int((payload or {}).get("latency_ms") or 0)
                data["latency_sum"] += latency
                data["latency_count"] += 1
            except Exception:
                pass
        elif event_type in ("details_loaded", "api_error"):
            data["details_requests"] += 1
            if event_type == "api_error":
                data["details_errors"] += 1

    # Format output chronologically
    out: list[dict[str, Any]] = []
    # Ensure all buckets in range appear, even if empty
    cur = bucket_start(window_start)
    while cur <= window_end:
        data = buckets.get(
            cur,
            {
                "searches": 0,
                "zero_searches": 0,
                "latency_sum": 0,
                "latency_count": 0,
                "details_requests": 0,
                "details_errors": 0,
            },
        )
        avg_latency = (
            int(data["latency_sum"] / data["latency_count"]) if data["latency_count"] else None
        )
        zero_rate = (data["zero_searches"] / data["searches"]) if data["searches"] else None
        error_rate = (
            (data["details_errors"] / data["details_requests"])
            if data["details_requests"]
            else None
        )
        out.append(
            {
                "hour_start": cur.isoformat(),
                "searches": data["searches"],
                "zero_searches": data["zero_searches"],
                "zero_rate": zero_rate,
                "avg_latency_ms": avg_latency,
                "details_requests": data["details_requests"],
                "details_errors": data["details_errors"],
                "details_error_rate": error_rate,
            }
        )
        cur = cur + timedelta(hours=1)

    return {"window_hours": hours, "buckets": out}


@app.get("/ui/telemetry/alerts")
def ui_telemetry_alerts(
    hours: int = Query(1, ge=1, le=168, description="Window size in hours"),
    zero_rate_gt: float = Query(
        0.5, ge=0.0, le=1.0, description="> threshold for zero-result rate"
    ),
    details_error_rate_gt: float = Query(
        0.2, ge=0.0, le=1.0, description="> threshold for details error rate"
    ),
    min_searches: int = Query(
        20, ge=0, description="Min searches in window to evaluate zero-result alert"
    ),
    min_details_requests: int = Query(
        10, ge=0, description="Min details requests in window to evaluate error alert"
    ),
    send: int = Query(
        0, description="If 1 and ALERT_WEBHOOK_URL is set, send alert payload to webhook"
    ),
) -> dict[str, Any]:
    """Evaluate recent telemetry and report alert conditions.

    - Aggregates over the last N hours (default 1).
    - Computes overall zero-result rate and details error rate.
    - If `send=1` and env var `ALERT_WEBHOOK_URL` is set, POSTs the alert JSON there.
    """
    metrics = ui_telemetry_metrics(hours=hours)
    buckets: list[dict[str, Any]] = metrics.get("buckets", [])

    searches = sum(int(b.get("searches") or 0) for b in buckets)
    zero_searches = sum(int(b.get("zero_searches") or 0) for b in buckets)
    details_requests = sum(int(b.get("details_requests") or 0) for b in buckets)
    details_errors = sum(int(b.get("details_errors") or 0) for b in buckets)

    zero_rate = (zero_searches / searches) if searches else None
    details_error_rate = (details_errors / details_requests) if details_requests else None

    zero_rate_alert = (
        zero_rate is not None and searches >= min_searches and zero_rate > zero_rate_gt
    )
    details_error_rate_alert = (
        details_error_rate is not None
        and details_requests >= min_details_requests
        and details_error_rate > details_error_rate_gt
    )

    alert_active = bool(zero_rate_alert or details_error_rate_alert)

    payload: dict[str, Any] = {
        "window_hours": hours,
        "searches": searches,
        "zero_searches": zero_searches,
        "zero_rate": zero_rate,
        "zero_rate_threshold": zero_rate_gt,
        "details_requests": details_requests,
        "details_errors": details_errors,
        "details_error_rate": details_error_rate,
        "details_error_rate_threshold": details_error_rate_gt,
        "min_searches": min_searches,
        "min_details_requests": min_details_requests,
        "alert_zero_rate": zero_rate_alert,
        "alert_details_error_rate": details_error_rate_alert,
        "alert_active": alert_active,
        "buckets": buckets,
    }

    # Optional webhook dispatch
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    sent = False
    if send == 1 and webhook_url and alert_active:
        try:
            import json as _json
            from urllib import request as _urlreq

            data = _json.dumps({"type": "ui_telemetry_alert", "payload": payload}).encode()
            req = _urlreq.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            # Best-effort; ignore failures
            _urlreq.urlopen(req, timeout=5)  # nosec B310
            sent = True
        except Exception:
            sent = False

    payload["webhook_sent"] = sent
    return payload


@app.get("/summaries")
def get_summaries(q: str | None = None, size: int = 10) -> dict[str, Any]:
    """Return summaries for top-N matches for a query (or latest if no query)."""
    client = _get_client()
    if q:
        query: dict[str, Any] = {
            "bool": {
                "must": {"multi_match": {"query": q, "fields": ["title^2", "abstract", "summary"]}}
            }
        }
    else:
        query = {"match_all": {}}
    res = client.search(
        index=INDEX_NAME,
        body={"query": query, "size": size, "sort": [{"fetched_at": {"order": "desc"}}]},
    )
    items: list[dict[str, Any]] = []
    for h in res.get("hits", {}).get("hits", []):
        src = h.get("_source", {}) or {}
        items.append(
            {
                "id": h.get("_id"),
                "title": src.get("title"),
                "summary": src.get("summary"),
                "abstract": src.get("abstract"),
                "year": src.get("year"),
                "citation_count": src.get("citation_count"),
            }
        )
    return {"total": res.get("hits", {}).get("total", {}).get("value", 0), "items": items}
