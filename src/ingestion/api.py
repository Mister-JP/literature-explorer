from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from opensearchpy import OpenSearch

from .config import Settings
from .db import Base, create_session_factory
from .models import Paper
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
) -> HTMLResponse:
    client = _get_client()
    must: list[dict[str, Any]] = []
    if q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": ["title^2", "abstract", "summary"],
                }
            }
        )
    query = {"bool": {"must": must or {"match_all": {}}}}
    res = client.search(
        index=INDEX_NAME,
        body={"query": query, "size": size, "sort": [{"fetched_at": {"order": "desc"}}]},
    )
    hits = [
        {
            "id": int(h.get("_id")) if str(h.get("_id")).isdigit() else h.get("_id"),
            **(h.get("_source", {}) or {}),
        }
        for h in res.get("hits", {}).get("hits", [])
    ][:size]
    # Render table with inline summary and expandable sections when available
    return templates.TemplateResponse(
        "ui_search.html",
        {
            "request": request,
            "q": q or "",
            "items": hits,
        },
    )


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
