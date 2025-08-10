from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from .connectors.base import PaperMetadata
from .dedup import is_duplicate
from .models import Paper
from .parser import extract_abstract_and_conclusion, parse_pdf_into_sections
from .storage import download_pdf_to_storage
from .utils import (
    TelemetryCounters,
    license_permits_pdf_storage,
    normalize_license,
    rate_limit_sleep,
)


@dataclass
class IngestResult:
    stored: int
    skipped: int
    errors: int


def ingest_records(
    records: Iterable[PaperMetadata],
    session_factory: sessionmaker,
    storage_dir: str,
    request_timeout_seconds: int,
    rate_limit_delay_seconds: int,
) -> IngestResult:
    counters = TelemetryCounters()
    with session_factory() as session:
        for rec in records:
            try:
                rec.license = normalize_license(rec.license)
                if is_duplicate(
                    session,
                    source=rec.source,
                    doi=rec.doi,
                    external_id=rec.external_id,
                    title=rec.title,
                    authors=rec.authors,
                ):
                    counters.skipped += 1
                    continue

                pdf_path: str | None = None
                permit_pdf = license_permits_pdf_storage(rec.license)
                # Dev/preview overrides: allow storing PDFs without explicit license when enabled
                if not permit_pdf and os.environ.get("ALLOW_PDF_WITHOUT_LICENSE", "0") == "1":
                    permit_pdf = True
                if (
                    not permit_pdf
                    and rec.source == "pmc"
                    and os.environ.get("ALLOW_PMC_PDF", "0") == "1"
                ):
                    permit_pdf = True

                if rec.pdf_url and permit_pdf:
                    file_hint = (
                        f"{rec.source}-{(rec.external_id or rec.doi or rec.title)[:80]}".strip("-")
                        + ".pdf"
                    )
                    pdf_path = download_pdf_to_storage(
                        rec.pdf_url,
                        storage_dir=storage_dir,
                        file_hint=file_hint,
                        timeout_seconds=request_timeout_seconds,
                    )
                    rate_limit_sleep(rate_limit_delay_seconds)

                # Initialize parsed sections if we have a PDF and can extract quickly (best-effort, non-fatal)
                sections: dict[str, str] = {}
                abstract_txt = rec.abstract
                conclusion_txt = None
                if pdf_path:
                    try:
                        sections = parse_pdf_into_sections(pdf_path)
                        abs2, concl2 = extract_abstract_and_conclusion(sections)
                        if abs2 and not abstract_txt:
                            abstract_txt = abs2
                        conclusion_txt = concl2
                    except Exception:
                        sections = {}

                paper = Paper(
                    source=rec.source,
                    external_id=rec.external_id,
                    doi=rec.doi,
                    title=rec.title,
                    authors={"list": rec.authors},
                    abstract=abstract_txt,
                    license=rec.license,
                    pdf_path=pdf_path,
                    sections=sections or {},
                    conclusion=conclusion_txt,
                    year=rec.year,
                    venue=rec.venue,
                    concepts={"list": rec.concepts or []},
                    citation_count=rec.citation_count,
                )
                session.add(paper)
                session.commit()
                counters.ingested += 1
            except Exception:  # noqa: BLE001
                session.rollback()
                counters.errors += 1

    return IngestResult(stored=counters.ingested, skipped=counters.skipped, errors=counters.errors)
