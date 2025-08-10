from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import ingestion.api as api_mod
from ingestion.api import app


class _FakeSearchClient:
    def __init__(self) -> None:
        self.last_index: str | None = None
        self.last_body: dict[str, Any] | None = None

    def search(self, *, index: str, body: dict[str, Any]) -> dict[str, Any]:  # type: ignore[override]
        self.last_index = index
        self.last_body = body
        # return minimal ES-like response
        return {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_id": "1", "_score": 1.0, "_source": {"title": "x"}}],
            }
        }


def test_search_builds_expected_filters(monkeypatch):
    fake = _FakeSearchClient()
    monkeypatch.setattr(api_mod, "_get_client", lambda: fake)

    client = TestClient(app)
    r = client.get(
        "/search",
        params={
            "q": "transformer",
            "author": "Alice",
            "year_start": 2020,
            "year_end": 2022,
            "license": "cc-by",
            "source": "openalex",
            "sort": "citations",
            "size": 10,
        },
    )
    assert r.status_code == 200
    assert r.json()["total"] == 1

    body = fake.last_body
    assert body is not None
    # Must include multi_match
    must = body["query"]["bool"]["must"]
    assert any("multi_match" in m for m in (must if isinstance(must, list) else [must]))
    # Filters include author, year range, license, source
    filters = body["query"]["bool"]["filter"]
    assert {"term": {"authors": "Alice"}} in filters
    assert {"term": {"license": "cc-by"}} in filters
    assert {"term": {"source": "openalex"}} in filters
    rng = next(f for f in filters if "range" in f)
    assert rng["range"]["year"]["gte"] == 2020
    assert rng["range"]["year"]["lte"] == 2022
    # Sort by citations
    assert body["sort"] == [{"citation_count": {"order": "desc"}}]
