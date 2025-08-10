from __future__ import annotations

import json
import time

import typer
from dotenv import load_dotenv

from .config import Settings
from .connectors.arxiv import ArxivConnector
from .db import Base, create_session_factory
from .dedup import is_duplicate
from .models import Paper
from .storage import download_pdf_to_storage, ensure_storage_dir


def _init_db(session_factory) -> None:
    # Create tables if not exist
    with session_factory() as session:
        engine = session.get_bind()
        Base.metadata.create_all(engine)


def main(
    query: str = typer.Option(..., "--query", help="Search query for arXiv"),
    max_results: int = typer.Option(10, "--max-results", help="Max results to fetch"),
):
    """Run a search against arXiv, store metadata and PDFs."""
    load_dotenv()
    settings = Settings.from_env()
    # Allow CLI override
    if max_results:
        settings.arxiv_max_results = max_results

    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    ensure_storage_dir(settings.storage_dir)

    connector = ArxivConnector()
    records = connector.search(query=query, max_results=settings.arxiv_max_results)

    stored = 0
    skipped = 0
    errors = 0

    with session_factory() as session:
        for rec in records:
            try:
                if is_duplicate(
                    session,
                    source=rec.source,
                    doi=rec.doi,
                    external_id=rec.external_id,
                    title=rec.title,
                    authors=rec.authors,
                ):
                    skipped += 1
                    continue

                pdf_path: str | None = None
                if rec.pdf_url:
                    file_hint = f"{rec.source}-{rec.external_id or ''}".strip("-") + ".pdf"
                    pdf_path = download_pdf_to_storage(
                        rec.pdf_url,
                        storage_dir=settings.storage_dir,
                        file_hint=file_hint,
                        timeout_seconds=settings.request_timeout_seconds,
                    )
                    time.sleep(settings.rate_limit_delay_seconds)

                paper = Paper(
                    source=rec.source,
                    external_id=rec.external_id,
                    doi=rec.doi,
                    title=rec.title,
                    authors={"list": rec.authors},
                    abstract=rec.abstract,
                    license=rec.license,
                    pdf_path=pdf_path,
                )
                session.add(paper)
                session.commit()
                stored += 1
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                errors += 1
                typer.secho(
                    f"Error processing record {rec.external_id}: {exc}", fg=typer.colors.RED
                )

    typer.echo(json.dumps({"stored": stored, "skipped": skipped, "errors": errors}))


if __name__ == "__main__":
    typer.run(main)
