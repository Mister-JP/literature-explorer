from __future__ import annotations

from collections.abc import Iterable

import arxiv  # type: ignore

from .base import Connector, PaperMetadata, PDFRef, QuerySpec


class ArxivConnector(Connector):
    source_name = "arxiv"

    def search(self, query: QuerySpec) -> Iterable[PaperMetadata]:
        # Construct arXiv query string from keywords and authors.
        # arXiv supports fielded queries like: all:"deep learning" AND au:"Smith"
        terms: list[str] = []
        if query.keywords:
            keyword_expr = " AND ".join(f'all:"{kw}"' for kw in query.keywords)
            terms.append(keyword_expr)
        if query.authors:
            author_expr = " AND ".join(f'au:"{a}"' for a in query.authors)
            terms.append(author_expr)
        qstr = " AND ".join(t for t in terms if t) or "all:*"

        max_results = query.max_results or 10
        search = arxiv.Search(
            query=qstr,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        for result in search.results():
            authors = [a.name for a in result.authors] if getattr(result, "authors", None) else []
            yield PaperMetadata(
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

    def fetch_pdf(self, item: PaperMetadata) -> PDFRef | None:
        if item.pdf_url:
            return PDFRef(url=item.pdf_url)
        return None
