from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
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

    must: list[dict[str, Any]] = []
    filter_q: list[dict[str, Any]] = []

    if q:
        must.append({"multi_match": {"query": q, "fields": ["title^2", "abstract"]}})
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

    res = client.search(index=INDEX_NAME, body={"query": query, "size": size, "sort": sort_clause})
    hits = [
        {
            "id": int(h.get("_id")) if str(h.get("_id")).isdigit() else h.get("_id"),
            "score": h.get("_score"),
            **h.get("_source", {}),
        }
        for h in res.get("hits", {}).get("hits", [])
    ]
    return {"total": res.get("hits", {}).get("total", {}).get("value", 0), "hits": hits}
