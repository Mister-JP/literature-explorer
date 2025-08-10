from __future__ import annotations

import os
from typing import Any

from opensearchpy import OpenSearch
from sqlalchemy import select

from .config import Settings
from .db import Base, create_session_factory
from .models import Paper

INDEX_NAME = os.environ.get("SEARCH_INDEX", "papers")


def _get_client() -> OpenSearch:
    host = os.environ.get("SEARCH_HOST", "http://localhost:9200")
    return OpenSearch(hosts=[host])


def ensure_index(client: OpenSearch) -> None:
    mapping: dict[str, Any] = {
        "settings": {
            "index": {"number_of_shards": 1, "number_of_replicas": 0},
            "analysis": {
                "analyzer": {
                    "english_custom": {
                        "type": "standard",
                        "stopwords": "_english_",
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                "title": {"type": "text", "analyzer": "english"},
                "abstract": {"type": "text", "analyzer": "english"},
                "summary": {"type": "text", "analyzer": "english"},
                "authors": {"type": "keyword"},
                "year": {"type": "integer"},
                "venue": {"type": "keyword"},
                "doi": {"type": "keyword"},
                "source": {"type": "keyword"},
                "license": {"type": "keyword"},
                "concepts": {"type": "keyword"},
                "citation_count": {"type": "integer"},
                "fetched_at": {"type": "date"},
                "semantic_score": {"type": "float"},
            }
        },
    }
    if not client.indices.exists(INDEX_NAME):
        client.indices.create(index=INDEX_NAME, body=mapping)


def upsert_document(client: OpenSearch, paper: Paper) -> None:
    doc = {
        "title": paper.title,
        "abstract": paper.abstract,
        "summary": paper.summary,
        "authors": paper.authors.get("list", []) if paper.authors else [],
        "year": paper.year,
        "venue": paper.venue,
        "doi": paper.doi,
        "source": paper.source,
        "license": paper.license,
        "concepts": paper.concepts.get("list", []) if paper.concepts else [],
        "citation_count": paper.citation_count,
        "fetched_at": paper.fetched_at.isoformat() if paper.fetched_at else None,
    }
    client.index(index=INDEX_NAME, id=str(paper.id), body=doc)


def main() -> None:
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    with session_factory() as session:
        engine = session.get_bind()
        Base.metadata.create_all(engine)

    client = _get_client()
    ensure_index(client)

    with session_factory() as session:
        for (paper,) in session.execute(select(Paper)):
            upsert_document(client, paper)


if __name__ == "__main__":
    main()
