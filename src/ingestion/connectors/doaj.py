from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import quote_plus

from ..utils import http_get_json
from .base import Connector, PaperMetadata, PDFRef, QuerySpec

BASE_URL = "https://doaj.org/api/v2/search/articles/"
FALLBACK_URL = "https://doaj.org/api/search/articles/"


class DOAJConnector(Connector):
    source_name = "doaj"

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:
        # Build a basic query string. DOAJ uses an Elasticsearch-like q parameter.
        q_parts: list[str] = []
        if query.keywords:
            q_parts.append(" ".join(query.keywords))
        if query.authors:
            # simple author tokens; DOAJ full query DSL is richer but this works for MVP
            q_parts.append(" ".join(query.authors))
        q = " ".join(q_parts) or "*"
        # DOAJ expects the query in the path instead of a `q` param
        path = BASE_URL + quote_plus(q)
        params = {"pageSize": str(query.max_results or 10)}
        try:
            data = http_get_json(
                path,
                params=params,
                timeout_seconds=30,
                source_name=self.source_name,
                min_interval_seconds=0.5,
            )
        except Exception:
            # Fallback for older DOAJ deployments
            fallback_path = FALLBACK_URL + quote_plus(q)
            data = http_get_json(
                fallback_path,
                params=params,
                timeout_seconds=30,
                source_name=self.source_name,
                min_interval_seconds=0.5,
            )

        for item in data.get("results", [])[: query.max_results or 10]:
            bib = item.get("bibjson", {}) or {}
            title = bib.get("title") or ""
            authors = [a.get("name", "") for a in (bib.get("author") or []) if isinstance(a, dict)]
            abstract = bib.get("abstract")
            year = None
            try:
                if bib.get("year") is not None:
                    year = int(bib.get("year"))  # type: ignore[arg-type]
            except Exception:  # noqa: BLE001
                year = None
            venue = None
            j = bib.get("journal") or {}
            if isinstance(j, dict):
                venue = j.get("title") or j.get("publisher")

            doi = None
            for ident in bib.get("identifier", []) or []:
                if isinstance(ident, dict) and ident.get("type") == "doi":
                    doi = ident.get("id")
                    break

            license_str = None
            lic = bib.get("license")
            if isinstance(lic, list) and lic:
                # take the first license's open access label or type
                first = lic[0]
                if isinstance(first, dict):
                    license_str = first.get("type") or first.get("title") or first.get("url")

            pdf_url = None
            for link in bib.get("link", []) or []:
                if not isinstance(link, dict):
                    continue
                if (link.get("type") or "").lower() in {
                    "application/pdf",
                    "pdf",
                    "fulltext",
                    "full-text",
                }:
                    pdf_url = link.get("url")
                    if pdf_url:
                        break

            yield PaperMetadata(
                source=self.source_name,
                external_id=item.get("id"),
                doi=doi,
                title=title,
                authors=[a for a in authors if a],
                abstract=abstract,
                license=license_str,
                pdf_url=pdf_url,
                year=year,
                venue=venue,
                concepts=[],
                citation_count=None,
            )

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:
        if item.pdf_url:
            return PDFRef(url=item.pdf_url)
        return None
