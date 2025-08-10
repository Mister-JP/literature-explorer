from __future__ import annotations

import re
from collections.abc import Iterable

from ..utils import http_get_json
from .base import Connector, PaperMetadata, PDFRef, QuerySpec

BASE_URL = "https://api.openalex.org/works"


class OpenAlexConnector(Connector):
    source_name = "openalex"

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:
        params: dict[str, str] = {
            "search": " ".join(query.keywords) if query.keywords else "",
            "per_page": str(query.max_results or 10),
        }
        filters: list[str] = []
        # If a DOI is present in keywords, use a direct DOI filter for precision
        doi_from_kw = None
        for kw in query.keywords or []:
            if isinstance(kw, str) and re.match(r"^10\.\S+/\S+", kw):
                doi_from_kw = kw
                break
        if doi_from_kw:
            filters.append(f"doi:{doi_from_kw}")
            params["per_page"] = "1"
            params["search"] = ""
        if query.authors:
            # OpenAlex filter by author.display_name.search
            filters.append(f"author.display_name.search:{' '.join(query.authors)}")
        if query.year_start is not None or query.year_end is not None:
            start = query.year_start or "1900"
            end = query.year_end or "2100"
            filters.append(f"from_publication_date:{start}-01-01")
            filters.append(f"to_publication_date:{end}-12-31")
        if filters:
            params["filter"] = ",".join(filters)

        data = http_get_json(
            BASE_URL,
            params=params,
            timeout_seconds=30,
            source_name=self.source_name,
            min_interval_seconds=0.5,
        )
        for item in data.get("results", [])[: query.max_results or 10]:
            doi = item.get("doi")
            title = item.get("title") or item.get("display_name") or ""
            authors = [
                a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])
            ]
            abstract = item.get("abstract") or None
            license_str = None
            oa_info = item.get("open_access", {})
            if isinstance(oa_info, dict):
                license_str = oa_info.get("license")
            concepts = [c.get("display_name", "") for c in item.get("concepts", [])]
            # Prefer explicit publication year when present, then try date fields
            year = None
            try:
                if item.get("publication_year") is not None:
                    year = int(item["publication_year"])  # type: ignore[arg-type]
                elif item.get("publication_date"):
                    year = int(str(item["publication_date"])[:4])
                elif item.get("from_publication_date"):
                    year = int(str(item["from_publication_date"])[:4])
            except Exception:  # noqa: BLE001
                year = None
            citation_count = item.get("cited_by_count")
            external_id = item.get("id")

            # best OA PDF if available
            pdf_url = None
            try:
                best_oa = item.get("best_oa_location") or {}
                if isinstance(best_oa, dict):
                    pdf_url = best_oa.get("pdf_url") or best_oa.get("url")
            except Exception:  # noqa: BLE001
                pdf_url = None

            yield PaperMetadata(
                source=self.source_name,
                external_id=external_id,
                doi=doi,
                title=title,
                authors=[a for a in authors if a],
                abstract=abstract,
                license=license_str,
                pdf_url=pdf_url,
                year=year,
                venue=(item.get("host_venue", {}) or {}).get("display_name"),
                concepts=[c for c in concepts if c],
                citation_count=citation_count,
            )

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:
        if item.pdf_url:
            return PDFRef(url=item.pdf_url)
        return None
