from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaperMetadata:
    source: str
    external_id: str | None
    doi: str | None
    title: str
    authors: list[str]
    abstract: str | None
    license: str | None
    pdf_url: str | None


class Connector:
    source_name: str

    def search(self, query: str, max_results: int = 10) -> list[PaperMetadata]:  # pragma: no cover
        raise NotImplementedError
