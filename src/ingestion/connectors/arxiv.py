from __future__ import annotations

import arxiv  # type: ignore

from .base import Connector, PaperMetadata


class ArxivConnector(Connector):
    source_name = "arxiv"

    def search(self, query: str, max_results: int = 10) -> list[PaperMetadata]:
        search = arxiv.Search(
            query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance
        )
        results: list[PaperMetadata] = []
        for result in search.results():
            authors = [a.name for a in result.authors] if getattr(result, "authors", None) else []
            metadata = PaperMetadata(
                source=self.source_name,
                external_id=(
                    result.get_short_id() if hasattr(result, "get_short_id") else result.entry_id
                ),
                doi=getattr(result, "doi", None),
                title=result.title.strip(),
                authors=authors,
                abstract=result.summary.strip() if getattr(result, "summary", None) else None,
                license=getattr(result, "license", None),
                pdf_url=result.pdf_url if getattr(result, "pdf_url", None) else None,
            )
            results.append(metadata)
        return results
