from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass
class QuerySpec:
    """Normalized query specification for connectors and search.

    - keywords: list of keyword terms to match (joined as source-specific query string)
    - authors: list of author names to filter by (exact or fuzzy depending on source)
    - year_start/year_end: inclusive range for publication year
    - sources: optional sources to limit to (e.g., ["openalex", "arxiv"]). Connectors may ignore.
    - license_filter: normalized license string to include only allowed results
    - max_results: soft cap on results to return
    """

    keywords: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    year_start: int | None = None
    year_end: int | None = None
    sources: list[str] = field(default_factory=list)
    license_filter: str | None = None
    max_results: int = 10


@dataclass
class PDFRef:
    """Reference to a PDF either by URL (remote) and/or local storage path."""

    url: str | None = None
    path: str | None = None


@dataclass
class PaperMetadata:
    # Core identity
    source: str
    external_id: str | None
    doi: str | None

    # Descriptive fields
    title: str
    authors: list[str]
    abstract: str | None = None
    license: str | None = None
    pdf_url: str | None = None

    # Optional enrichment for Phase-2
    year: int | None = None
    venue: str | None = None
    concepts: list[str] = field(default_factory=list)
    citation_count: int | None = None


class Connector:
    source_name: str

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:  # pragma: no cover
        """Yield normalized metadata records for the given query spec."""
        raise NotImplementedError

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:  # pragma: no cover
        """Optionally return a PDF reference for a given item.

        Implementations may simply return the `pdf_url` embedded in the item when available.
        The ingestion layer is responsible for applying license policy and downloading if allowed.
        """
        raise NotImplementedError
