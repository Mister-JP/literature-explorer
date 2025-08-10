from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

import pytest
import vcr

from ingestion.connectors.base import Connector, PaperMetadata, QuerySpec
from ingestion.connectors.core import COREConnector
from ingestion.connectors.doaj import DOAJConnector
from ingestion.connectors.openalex import OpenAlexConnector
from ingestion.connectors.pmc import PMCConnector
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

# Optionally include CORE and PMC when explicitly requested (require API key / live)
if os.environ.get("INCLUDE_CORE", "0") == "1":
    CONNECTORS.append(("core", COREConnector))
if os.environ.get("INCLUDE_PMC", "0") == "1":
    CONNECTORS.append(("pmc", PMCConnector))


def test_connector_core_requires_api_key(monkeypatch):
    # Only run this check when CORE is not included live
    if os.environ.get("INCLUDE_CORE", "0") == "1":
        return
    monkeypatch.delenv("CORE_API_KEY", raising=False)
    c = COREConnector()
    with pytest.raises(RuntimeError):
        list(c.search(QuerySpec(keywords=["test"], max_results=1)))


def test_connector_pmc_smoke(monkeypatch):
    # Only run this live when explicitly requested; otherwise, just construct and no-call
    if os.environ.get("INCLUDE_PMC", "0") == "1":
        return
    # Ensure constructing PMC connector does not raise
    _ = PMCConnector()


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


def test_pmc_with_cassette_when_not_live():
    # Provide a recorded cassette for PMC to validate shape without hitting network
    if os.environ.get("INCLUDE_PMC", "0") == "1":
        pytest.skip("Live PMC run enabled; cassette test not needed")
    cassette = _cassette_path("pmc")
    if not cassette.exists():
        pytest.skip("PMC cassette not present")
    with vcr.use_cassette(str(cassette), record_mode="none"):
        connector: Connector = PMCConnector()
        # Match the recorded cassette query params (term=transformer, retmax=2)
        spec = QuerySpec(keywords=["transformer"], max_results=2)
        items = list(connector.search(spec))
        assert items and isinstance(items[0].title, str)


def test_core_with_cassette_when_not_live(monkeypatch):
    # Use recorded cassette for CORE to avoid needing API key in tests
    if os.environ.get("INCLUDE_CORE", "0") == "1":
        pytest.skip("Live CORE run enabled; cassette test not needed")
    cassette = _cassette_path("core")
    if not cassette.exists():
        pytest.skip("CORE cassette not present")
    # Ensure API key matches the cassette by reading it from the recorded URI
    from urllib.parse import parse_qsl, urlparse

    import yaml

    with open(cassette, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    interactions = (data or {}).get("interactions", [])
    if not interactions:
        pytest.skip("CORE cassette has no interactions")
    first_uri = interactions[0]["request"]["uri"]
    query_params = dict(parse_qsl(urlparse(first_uri).query))
    api_key = query_params.get("apiKey")
    if not api_key:
        pytest.skip("CORE cassette missing apiKey in URI")
    monkeypatch.setenv("CORE_API_KEY", api_key)

    with vcr.use_cassette(str(cassette), record_mode="none"):
        connector: Connector = COREConnector()
        # Match the recorded cassette query params (limit=2, q=transformer)
        spec = QuerySpec(keywords=["transformer"], max_results=2)
        items = list(connector.search(spec))
        assert items and isinstance(items[0].title, str)
