from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pytest
import vcr

from ingestion.connectors.base import Connector, PaperMetadata, QuerySpec
from ingestion.connectors.doaj import DOAJConnector
from ingestion.connectors.openalex import OpenAlexConnector
from ingestion.connectors.semanticscholar import SemanticScholarConnector

CASSETTES_DIR = Path(__file__).parent / "cassettes"
CASSETTES_DIR.mkdir(exist_ok=True)


CONNECTORS: list[tuple[str, type[Connector]]] = [
    ("openalex", OpenAlexConnector),
    ("semanticscholar", SemanticScholarConnector),
]

# Optionally include DOAJ when explicitly requested (API shape can vary)
if os.environ.get("INCLUDE_DOAJ", "0") == "1":
    CONNECTORS.append(("doaj", DOAJConnector))


def _cassette_path(name: str) -> Path:
    return CASSETTES_DIR / f"connector_{name}.yaml"


def _should_run_live(name: str) -> bool:
    # To avoid playback incompatibilities across urllib3 versions, require live runs explicitly.
    return os.environ.get("RUN_LIVE", "0") == "1"


@pytest.mark.parametrize("name,cls", CONNECTORS)
def test_connector_basic_conformance(name: str, cls: type[Connector]):
    if not _should_run_live(name):
        pytest.skip("RUN_LIVE!=1")

    # Live-only to avoid VCR playback differences across environments
    with vcr.use_cassette(str(_cassette_path(name)), record_mode="new_episodes"):
        connector: Connector = cls()
        spec = QuerySpec(keywords=["transformer"], max_results=2)
        out: Iterable[PaperMetadata] = connector.search(spec)
        items = list(out)

    assert len(items) > 0
    # Validate shape of PaperMetadata
    first = items[0]
    assert first.source == name or isinstance(first.source, str)
    assert isinstance(first.title, str) and first.title
    assert isinstance(first.authors, list)
    # optional fields may be None; simply check attributes exist
    _ = first.doi
    _ = first.abstract
    _ = first.license
    _ = first.pdf_url
    _ = first.year
    _ = first.venue
    _ = first.concepts
    _ = first.citation_count
