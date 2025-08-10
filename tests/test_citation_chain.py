from __future__ import annotations

import os
from collections.abc import Iterable

import pytest

from ingestion.citations import fetch_openalex_neighbors
from ingestion.connectors.base import PaperMetadata
from ingestion.db import Base, create_session_factory, ensure_schema
from ingestion.ingest import ingest_records


def test_citation_chain_ingest_dedup(tmp_path):
    # Use a throwaway SQLite DB
    db_url = f"sqlite:///{tmp_path}/test.db"
    session_factory = create_session_factory(db_url)
    with session_factory() as session:
        engine = session.get_bind()
        ensure_schema(Base, engine)

    # Simulate 25 neighbor DOIs
    dois = [f"10.1234/test.{i}" for i in range(25)]

    def build_records(doilist: list[str]) -> Iterable[PaperMetadata]:
        for i, d in enumerate(doilist):
            yield PaperMetadata(
                source="test",
                external_id=f"ext-{i}",
                doi=d,
                title=f"Title {i}",
                authors=["Alice", "Bob"],
                abstract=None,
                license="cc-by",
                pdf_url=None,
                year=2024,
                venue="TestConf",
                concepts=[],
                citation_count=0,
            )

    # First ingest
    res1 = ingest_records(
        build_records(dois),
        session_factory=session_factory,
        storage_dir=str(tmp_path),
        request_timeout_seconds=1,
        rate_limit_delay_seconds=0,
    )
    assert res1.stored == len(dois) and res1.errors == 0

    # Second ingest (should dedup)
    res2 = ingest_records(
        build_records(dois),
        session_factory=session_factory,
        storage_dir=str(tmp_path),
        request_timeout_seconds=1,
        rate_limit_delay_seconds=0,
    )
    assert res2.stored == 0 and res2.skipped == len(dois)


def test_fetch_openalex_neighbors_live():
    if os.environ.get("RUN_LIVE", "0") != "1":
        pytest.skip("RUN_LIVE!=1")
    # A well-cited DOI to get neighbors. Adjust if provider changes.
    seed = "10.1038/nature14539"  # AlphaGo (example)
    neighbors = fetch_openalex_neighbors(seed)
    assert isinstance(neighbors, list)
    # Expect at least some neighbors; threshold low to avoid flakiness
    assert len(neighbors) >= 10
