from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ingestion.connectors.base import PaperMetadata
from ingestion.db import Base, create_session_factory, ensure_schema
from ingestion.ingest import ingest_records


def _records() -> Iterable[PaperMetadata]:
    # Restricted license should prevent any PDF download
    yield PaperMetadata(
        source="test",
        external_id="x1",
        doi="10.9999/test.1",
        title="A test paper",
        authors=["Alice", "Bob"],
        abstract="...",
        license="all-rights-reserved",
        pdf_url="http://example.invalid/test.pdf",
        year=2024,
        venue="TestConf",
        concepts=["NLP"],
        citation_count=0,
    )


def test_ingestion_does_not_store_pdf_for_restricted_license(tmp_path: Path):
    # Use in-memory SQLite
    session_factory = create_session_factory("sqlite+pysqlite:///:memory:")
    # Ensure schema
    with session_factory() as session:
        engine = session.get_bind()
        ensure_schema(Base, engine)

    res = ingest_records(
        _records(),
        session_factory=session_factory,
        storage_dir=str(tmp_path),
        request_timeout_seconds=1,
        rate_limit_delay_seconds=0,
    )
    assert res.stored == 1
    assert res.errors == 0

    # Ensure no file was created in storage
    assert not any(tmp_path.iterdir())
