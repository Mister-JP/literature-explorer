from __future__ import annotations

from collections.abc import Iterable

from ..utils import http_get_json
from .base import Connector, PaperMetadata, PDFRef, QuerySpec

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarConnector(Connector):
    source_name = "semanticscholar"

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:
        # Build query string; Semantic Scholar supports a simple query parameter
        q = " ".join(query.keywords or [])
        if query.authors:
            q = (q + " " + " ".join(query.authors)).strip()

        params: dict[str, str] = {
            "query": q or "*",
            "offset": "0",
            "limit": str(query.max_results or 10),
            "fields": "title,abstract,authors,year,venue,externalIds,openAccessPdf,citationCount",
        }
        data = http_get_json(
            BASE_URL,
            params=params,
            timeout_seconds=30,
            source_name=self.source_name,
            min_interval_seconds=0.5,
        )
        for item in data.get("data", [])[: query.max_results or 10]:
            external_ids = item.get("externalIds") or {}
            doi = external_ids.get("DOI")
            title = item.get("title") or ""
            authors = [a.get("name", "") for a in (item.get("authors") or [])]
            abstract = item.get("abstract")
            year = item.get("year")
            venue = item.get("venue")
            citation_count = item.get("citationCount")
            pdf_url = None
            oa = item.get("openAccessPdf") or {}
            if isinstance(oa, dict):
                pdf_url = oa.get("url")

            yield PaperMetadata(
                source=self.source_name,
                external_id=item.get("paperId"),
                doi=doi,
                title=title,
                authors=[a for a in authors if a],
                abstract=abstract,
                license=None,  # license not directly provided in this endpoint
                pdf_url=pdf_url,
                year=year,
                venue=venue,
                concepts=[],
                citation_count=citation_count,
            )

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:
        if item.pdf_url:
            return PDFRef(url=item.pdf_url)
        return None
