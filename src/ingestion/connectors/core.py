from __future__ import annotations

import os
from collections.abc import Iterable

from ..utils import http_get_json
from .base import Connector, PaperMetadata, PDFRef, QuerySpec

BASE_URL = "https://api.core.ac.uk/v3/search/works"


class COREConnector(Connector):
    source_name = "core"

    def _auth_params(self) -> dict[str, str]:
        api_key = os.environ.get("CORE_API_KEY")
        if not api_key:
            # Allow code to exist without runtime key; callers should provide it when using this connector.
            raise RuntimeError("CORE_API_KEY is required to use the CORE connector")
        return {"apiKey": api_key}

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:
        params: dict[str, str] = {
            "q": " ".join(query.keywords) if query.keywords else "*",
            "limit": str(query.max_results or 10),
        }
        params.update(self._auth_params())
        data = http_get_json(
            BASE_URL,
            params=params,
            timeout_seconds=30,
            source_name=self.source_name,
            min_interval_seconds=0.5,
        )
        for item in data.get("results", [])[: query.max_results or 10]:
            # CORE v3 shape reference (may vary):
            # id, doi, title, authors [{name}], yearPublished, publisher, oa, downloadUrl, topics, citationsCount
            title = item.get("title") or ""
            authors = [
                a.get("name", "") for a in (item.get("authors") or []) if isinstance(a, dict)
            ]
            doi = item.get("doi")
            year = item.get("yearPublished") or item.get("year")
            try:
                year = int(year) if year is not None else None
            except Exception:  # noqa: BLE001
                year = None
            citation_count = item.get("citationsCount")
            license_str = item.get("license") or item.get("licence") or None
            pdf_url = item.get("downloadUrl") or None
            external_id = str(item.get("id")) if item.get("id") is not None else None

            yield PaperMetadata(
                source=self.source_name,
                external_id=external_id,
                doi=doi,
                title=title,
                authors=[a for a in authors if a],
                abstract=item.get("abstract") or None,
                license=license_str,
                pdf_url=pdf_url,
                year=year,
                venue=item.get("publisher") or None,
                concepts=[t for t in (item.get("topics") or []) if isinstance(t, str)],
                citation_count=citation_count,
            )

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:
        if item.pdf_url:
            return PDFRef(url=item.pdf_url)
        return None
