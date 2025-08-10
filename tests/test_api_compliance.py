from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ingestion.api import app
from ingestion.db import Base, create_session_factory, ensure_schema
from ingestion.models import Paper


@pytest.fixture(autouse=True)
def _set_test_db(tmp_path) -> Iterator[None]:
    os.environ["DATABASE_URL"] = "sqlite:///" + str(tmp_path / "test.db")
    # ensure schema
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        engine = session.get_bind()
        ensure_schema(Base, engine)
    yield


def _insert_papers():
    session_factory = create_session_factory(os.environ["DATABASE_URL"])
    with session_factory() as session:
        p1 = Paper(
            source="test",
            external_id="a1",
            doi="10.1111/test.1",
            title="Open Paper",
            authors={"list": ["Alice"]},
            abstract=None,
            license="cc-by",
            pdf_path="/tmp/open.pdf",
        )
        p2 = Paper(
            source="test",
            external_id="a2",
            doi="10.1111/test.2",
            title="Restricted Paper",
            authors={"list": ["Bob"]},
            abstract=None,
            license="all-rights-reserved",
            pdf_path="/tmp/restricted.pdf",
        )
        session.add_all([p1, p2])
        session.commit()
        return p1.id, p2.id


def test_get_paper_enforces_no_serve_pdf():
    id_open, id_restricted = _insert_papers()
    client = TestClient(app)

    r1 = client.get(f"/paper/{id_open}")
    assert r1.status_code == 200
    assert r1.json()["pdf_path"] == "/tmp/open.pdf"

    r2 = client.get(f"/paper/{id_restricted}")
    assert r2.status_code == 200
    assert r2.json()["pdf_path"] is None
