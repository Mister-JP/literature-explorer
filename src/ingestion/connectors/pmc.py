from __future__ import annotations

from collections.abc import Iterable

from ..utils import http_get_json
from .base import Connector, PaperMetadata, PDFRef, QuerySpec

EUTILS_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EUTILS_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PMCConnector(Connector):
    source_name = "pmc"

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:
        # Use PMC (PubMed Central) open access subset via eutils; retrieve PMCID list, then summarize
        term = " ".join(query.keywords or ["open access"])  # basic keyword search
        params = {
            "db": "pmc",
            "retmode": "json",
            "retmax": str(query.max_results or 10),
            "term": term,
        }
        search_res = http_get_json(
            EUTILS_SEARCH,
            params=params,
            timeout_seconds=30,
            source_name=self.source_name,
            min_interval_seconds=0.4,
        )
        idlist = ((search_res.get("esearchresult") or {}).get("idlist") or [])[
            : query.max_results or 10
        ]
        if not idlist:
            return []
        summ_params = {
            "db": "pmc",
            "retmode": "json",
            "id": ",".join(idlist),
        }
        summaries = http_get_json(
            EUTILS_SUMMARY,
            params=summ_params,
            timeout_seconds=30,
            source_name=self.source_name,
            min_interval_seconds=0.4,
        )
        result = summaries.get("result") or {}
        for pmcid in idlist:
            item = result.get(pmcid) or {}
            title = item.get("title") or ""
            authors = [
                a.get("name", "") for a in (item.get("authors") or []) if isinstance(a, dict)
            ]
            year = None
            try:
                if item.get("pubdate"):
                    year = int(str(item["pubdate"])[:4])
            except Exception:  # noqa: BLE001
                year = None
            doi = None
            articleids = item.get("articleids") or []
            for aid in articleids:
                if isinstance(aid, dict) and aid.get("idtype") == "doi":
                    doi = aid.get("value")
                    break
            pdf_url = None
            elocationid = item.get("elocationid") or ""
            if elocationid:
                # Construct PMC OA PDF URL pattern when available
                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{elocationid}/pdf"
            yield PaperMetadata(
                source=self.source_name,
                external_id=pmcid,
                doi=doi,
                title=title,
                authors=[a for a in authors if a],
                abstract=None,
                license=item.get("license") or None,
                pdf_url=pdf_url,
                year=year,
                venue=item.get("source") or None,
                concepts=[],
                citation_count=None,
            )

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:
        if item.pdf_url:
            return PDFRef(url=item.pdf_url)
        return None
