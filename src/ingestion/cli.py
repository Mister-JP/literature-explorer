from __future__ import annotations

import json

import typer
import yaml
from dotenv import load_dotenv

from .citations import fetch_openalex_neighbors
from .config import Settings
from .connectors.arxiv import ArxivConnector
from .connectors.base import PaperMetadata, QuerySpec
from .connectors.core import COREConnector
from .connectors.doaj import DOAJConnector
from .connectors.openalex import OpenAlexConnector
from .connectors.pmc import PMCConnector
from .connectors.semanticscholar import SemanticScholarConnector
from .db import Base, create_session_factory, ensure_schema
from .ingest import ingest_records
from .parser import (
    extract_abstract_and_conclusion,
    parse_pdf_into_sections,
)
from .parser_grobid import grobid_parse_pdf
from .storage import ensure_storage_dir
from .summarizer import extractive_summary, summarize_sections


def _init_db(session_factory) -> None:
    # Create tables if not exist
    with session_factory() as session:
        engine = session.get_bind()
        ensure_schema(Base, engine)


def _normalize_license(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    # simple normalization for CC licenses
    cc_map = {
        "cc-by": "cc-by",
        "cc by": "cc-by",
        "cc-by-sa": "cc-by-sa",
        "cc by-sa": "cc-by-sa",
        "cc0": "cc0",
        "public domain": "public-domain",
    }
    for k, v in cc_map.items():
        if k in s:
            return v
    return s


def main(
    query: str = typer.Option(..., "--query", help="Search query (keywords)"),
    author: str | None = typer.Option(None, "--author", help="Author filter (exact match)"),
    max_results: int = typer.Option(10, "--max-results", help="Max results to fetch"),
    source: str = typer.Option(
        "arxiv", "--source", help="Data source: arxiv|openalex|semanticscholar|doaj|core|pmc"
    ),
):
    """Run a search against the selected source, store metadata and PDFs (license permitting)."""
    load_dotenv()
    settings = Settings.from_env()
    # Allow CLI override
    if max_results:
        settings.arxiv_max_results = max_results

    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    ensure_storage_dir(settings.storage_dir)

    connector = {
        "arxiv": ArxivConnector(),
        "openalex": OpenAlexConnector(),
        "semanticscholar": SemanticScholarConnector(),
        "doaj": DOAJConnector(),
        "core": COREConnector(),
        "pmc": PMCConnector(),
    }.get(source, ArxivConnector())
    spec = QuerySpec(
        keywords=[query] if query else [],
        authors=[author] if author else [],
        max_results=settings.arxiv_max_results,
    )
    records = connector.search(spec)

    res = ingest_records(
        records,
        session_factory=session_factory,
        storage_dir=settings.storage_dir,
        request_timeout_seconds=settings.request_timeout_seconds,
        rate_limit_delay_seconds=settings.rate_limit_delay_seconds,
    )

    typer.echo(json.dumps({"stored": res.stored, "skipped": res.skipped, "errors": res.errors}))


app = typer.Typer(add_completion=False)


@app.command("run")
def cmd_run(
    query: str = typer.Option(..., "--query"),
    author: str | None = typer.Option(None, "--author"),
    max_results: int = typer.Option(10, "--max-results"),
    source: str = typer.Option(
        "arxiv", "--source", help="Data source: arxiv|openalex|semanticscholar|doaj|core|pmc"
    ),
):
    main(query=query, author=author, max_results=max_results, source=source)


@app.command("hydrate-citations")
def cmd_hydrate_citations(
    seed_doi: str = typer.Argument(..., help="Seed DOI to expand"),
    depth: int = typer.Option(1, "--depth", min=1, max=2),
    max_per_level: int = typer.Option(25, "--max-per-level", min=1, max=100),
    source: str = typer.Option(
        "openalex", "--source", help="Connector used to ingest discovered DOIs"
    ),
    neighbors_file: str | None = typer.Option(
        None,
        "--neighbors-file",
        help="Optional path to a text file containing one DOI per line; when provided, uses these DOIs instead of calling the provider",
    ),
):
    """Fetch citation neighbors via OpenAlex and enqueue ingestion for discovered DOIs."""
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    ensure_storage_dir(settings.storage_dir)

    # Offline mode: ingest from file of DOIs directly (deterministic demonstration)
    if neighbors_file:
        try:
            with open(neighbors_file, encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        except Exception as exc:  # noqa: BLE001
            typer.secho(f"failed to read neighbors file: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=2) from None

        count = 0
        for i, doi in enumerate(lines[: max_per_level * depth]):
            pm = PaperMetadata(
                source="offline",
                external_id=f"offline-{i}",
                doi=doi,
                title=f"Offline Chain Paper {i}",
                authors=["Chain Author"],
                abstract=None,
                license="cc-by",
                pdf_url=None,
                year=2024,
                venue="OfflineVenue",
                concepts=["demo"],
                citation_count=0,
            )
            ingest_records(
                [pm],
                session_factory=session_factory,
                storage_dir=settings.storage_dir,
                request_timeout_seconds=settings.request_timeout_seconds,
                rate_limit_delay_seconds=settings.rate_limit_delay_seconds,
            )
            count += 1
        typer.echo(json.dumps({"ingested_offline": count}))
        return

    # Live mode: expand via provider
    frontier = [seed_doi]
    seen = set(frontier)
    for _ in range(depth):
        next_level: list[str] = []
        for doi in frontier:
            try:
                neighbors = fetch_openalex_neighbors(doi)[:max_per_level]
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"citation fetch failed for {doi}: {exc}", fg=typer.colors.RED)
                neighbors = []
            for ndoi in neighbors:
                if ndoi in seen:
                    continue
                seen.add(ndoi)
                connector = {
                    "arxiv": ArxivConnector(),
                    "openalex": OpenAlexConnector(),
                    "semanticscholar": SemanticScholarConnector(),
                    "doaj": DOAJConnector(),
                    "core": COREConnector(),
                    "pmc": PMCConnector(),
                }.get(source, OpenAlexConnector())
                spec = QuerySpec(keywords=[ndoi], max_results=1)
                ingest_records(
                    connector.search(spec),
                    session_factory=session_factory,
                    storage_dir=settings.storage_dir,
                    request_timeout_seconds=settings.request_timeout_seconds,
                    rate_limit_delay_seconds=settings.rate_limit_delay_seconds,
                )
            next_level.extend(neighbors)
        frontier = next_level


@app.command("reindex")
def cmd_reindex():
    from .indexer import main as reindex_main

    reindex_main()


@app.command("sweep-file")
def cmd_sweep_file(
    file: str = typer.Argument("sweeps.yaml"),
):
    """Run a series of sweeps defined in a YAML file.

    YAML structure:
      - query: "large language models"
        source: openalex
        max_results: 10
        author: "J. Smith"
    """
    load_dotenv()
    with open(file, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    if not isinstance(items, list):
        typer.secho("sweeps file must be a list", fg=typer.colors.RED)
        raise typer.Exit(code=2)
    for idx, item in enumerate(items, start=1):
        q = (item or {}).get("query")
        if not q:
            typer.secho(f"skipping item {idx}: missing query", fg=typer.colors.YELLOW)
            continue
        author = (item or {}).get("author")
        source = (item or {}).get("source", "openalex")
        max_results = int((item or {}).get("max_results", 10))
        typer.echo(
            f"[sweep {idx}] source={source} query=\"{q}\" author={author or ''} max={max_results}"
        )
        main(query=q, author=author, max_results=max_results, source=source)


@app.command("sweep-daemon")
def cmd_sweep_daemon(
    file: str = typer.Option("sweeps.yaml", "--file", help="Sweeps YAML file"),
    interval_seconds: int = typer.Option(
        3600, "--interval", min=10, help="Seconds between full sweeps"
    ),
    max_loops: int = typer.Option(0, "--max-loops", help="Stop after N loops (0 = forever)"),
):
    """Run sweeps from a YAML file in a loop with a fixed interval.

    Useful as a lightweight scheduler alternative to Celery for Phase-2.
    """
    import time

    typer.echo(f"Starting sweep daemon: file={file} interval={interval_seconds}s")
    loops = 0
    try:
        while True:
            loops += 1
            typer.echo(f"[sweep-daemon] loop={loops}")
            try:
                cmd_sweep_file(file)
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"sweep run failed: {exc}", fg=typer.colors.RED)

            if max_loops and loops >= max_loops:
                typer.echo("Max loops reached; exiting sweep-daemon")
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("Sweep daemon interrupted; exiting")


@app.command("parse-new")
def cmd_parse_new():
    """Parse any papers with stored PDFs that lack parsed sections and store sections + abstract/conclusion."""
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    from sqlalchemy import select

    from .models import Paper

    updated = 0
    with session_factory() as session:
        for (paper,) in session.execute(select(Paper)):
            if not paper.pdf_path or (paper.sections and len(paper.sections) > 0):
                continue
            try:
                paper.parse_attempts = (paper.parse_attempts or 0) + 1
                if settings.parser_backend == "grobid":
                    sections = grobid_parse_pdf(paper.pdf_path, host=settings.grobid_host)
                    if not sections:
                        # fallback to pdfminer if grobid failed
                        sections = parse_pdf_into_sections(paper.pdf_path)
                else:
                    sections = parse_pdf_into_sections(paper.pdf_path)
            except Exception as exc:  # noqa: BLE001
                paper.parse_error = str(exc)[:1000]
                session.add(paper)
                session.commit()
                typer.secho(f"parse failed for paper id={paper.id}: {exc}", fg=typer.colors.RED)
                continue
            paper.sections = sections or {}
            abstract, conclusion = extract_abstract_and_conclusion(paper.sections)
            if abstract and not paper.abstract:
                paper.abstract = abstract
            paper.conclusion = conclusion
            session.add(paper)
            session.commit()
            updated += 1
    typer.echo(json.dumps({"parsed": updated}))


@app.command("summarize-new")
def cmd_summarize_new():
    """Generate summaries for papers that have parsed sections but no summary yet."""
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    from sqlalchemy import select

    from .models import Paper

    updated = 0
    with session_factory() as session:
        for (paper,) in session.execute(select(Paper)):
            if paper.summary:
                continue
            summary: str | None = None
            if paper.sections:
                summary = summarize_sections(paper.sections)
            elif paper.abstract:
                summary = extractive_summary(paper.abstract, max_sentences=5, max_chars=1000)
            paper.summary = summary[:1000] if summary else None
            session.add(paper)
            session.commit()
            updated += 1
    typer.echo(json.dumps({"summarized": updated}))


@app.command("retro-parse")
def cmd_retro_parse(
    backup_file: str | None = typer.Option(
        None,
        "--backup-file",
        help="Optional path to write JSONL backup of fields that may be modified (id, sections, abstract, conclusion, summary, parse_attempts, parse_error)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Do not modify the database; report counts of items that would be parsed/summarized",
    ),
):
    """Backfill: parse sections and generate summaries for all existing PDFs, overwriting empty fields only.

    Safety:
      - Use --backup-file to write a JSONL snapshot of mutable fields prior to changes.
      - Use --dry-run to audit what would change without modifying data.
    """
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    from sqlalchemy import select

    from .models import Paper

    parsed = 0
    summarized = 0
    with session_factory() as session:
        # Optional backup of mutable fields before any modification
        if backup_file:
            try:
                with open(backup_file, "w", encoding="utf-8") as bf:
                    for (paper,) in session.execute(select(Paper)):
                        snapshot = {
                            "id": paper.id,
                            "sections": paper.sections or {},
                            "abstract": paper.abstract,
                            "conclusion": paper.conclusion,
                            "summary": paper.summary,
                            "parse_attempts": int(paper.parse_attempts or 0),
                            "parse_error": paper.parse_error,
                        }
                        bf.write(json.dumps(snapshot) + "\n")
                typer.secho(f"backup written: {backup_file}", fg=typer.colors.GREEN)
            except Exception as exc:  # noqa: BLE001
                typer.secho(f"failed to write backup file: {exc}", fg=typer.colors.RED)
                raise typer.Exit(code=2) from None

        if dry_run:
            would_parse = 0
            would_summarize = 0
            for (paper,) in session.execute(select(Paper)):
                if paper.pdf_path and not paper.sections:
                    would_parse += 1
                if (paper.sections and not paper.summary) or (
                    not paper.sections and paper.abstract and paper.pdf_path
                ):
                    # Either will summarize from sections once parsed, or from abstract if sections remain unavailable
                    would_summarize += 1
            typer.echo(
                json.dumps(
                    {
                        "dry_run": True,
                        "would_parse": would_parse,
                        "would_summarize": would_summarize,
                    }
                )
            )
            return

        for (paper,) in session.execute(select(Paper)):
            if not paper.pdf_path:
                continue
            if not paper.sections:
                try:
                    paper.parse_attempts = (paper.parse_attempts or 0) + 1
                    if settings.parser_backend == "grobid":
                        sections = grobid_parse_pdf(paper.pdf_path, host=settings.grobid_host)
                        if not sections:
                            sections = parse_pdf_into_sections(paper.pdf_path)
                    else:
                        sections = parse_pdf_into_sections(paper.pdf_path)
                except Exception as exc:  # noqa: BLE001
                    paper.parse_error = str(exc)[:1000]
                    session.add(paper)
                    session.commit()
                    typer.secho(
                        f"retro-parse failed for paper id={paper.id}: {exc}", fg=typer.colors.RED
                    )
                    continue
                paper.sections = sections or {}
                abstract, conclusion = extract_abstract_and_conclusion(paper.sections)
                if abstract and not paper.abstract:
                    paper.abstract = abstract
                if conclusion and not paper.conclusion:
                    paper.conclusion = conclusion
                parsed += 1
            if paper.sections and not paper.summary:
                summary = summarize_sections(paper.sections)
                paper.summary = summary[:1000] if summary else None
                summarized += 1
            session.add(paper)
            session.commit()
    typer.echo(json.dumps({"parsed": parsed, "summarized": summarized}))


@app.command("retry-parses")
def cmd_retry_parses(max_retries: int = typer.Option(3, "--max-retries")):
    """Retry parsing for papers with previous parse errors and attempts < max."""
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    from sqlalchemy import select

    from .models import Paper

    retried = 0
    with session_factory() as session:
        for (paper,) in session.execute(select(Paper)):
            attempts = int(paper.parse_attempts or 0)
            if not paper.pdf_path or (paper.sections and len(paper.sections) > 0):
                continue
            if attempts >= max_retries and paper.parse_error:
                continue
            try:
                paper.parse_attempts = attempts + 1
                if settings.parser_backend == "grobid":
                    sections = grobid_parse_pdf(paper.pdf_path, host=settings.grobid_host)
                    if not sections:
                        sections = parse_pdf_into_sections(paper.pdf_path)
                else:
                    sections = parse_pdf_into_sections(paper.pdf_path)
                paper.sections = sections or {}
                abstract, conclusion = extract_abstract_and_conclusion(paper.sections)
                if abstract and not paper.abstract:
                    paper.abstract = abstract
                if conclusion and not paper.conclusion:
                    paper.conclusion = conclusion
                paper.parse_error = None
                session.add(paper)
                session.commit()
                retried += 1
            except Exception as exc:  # noqa: BLE001
                paper.parse_error = str(exc)[:1000]
                session.add(paper)
                session.commit()
                continue
    typer.echo(json.dumps({"retried": retried}))


@app.command("coverage-counts")
def cmd_coverage_counts():
    """Print counts of parsing/summarization coverage.

    Reports totals for:
    - with_pdf: papers having a stored PDF path
    - with_sections: papers with non-empty sections
    - with_abstract_and_conclusion: papers with both abstract and conclusion
    - with_summary: papers with a summary
    """
    from sqlalchemy import select

    from .models import Paper

    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)

    with session_factory() as session:
        with_pdf = 0
        with_sections = 0
        with_abs_concl = 0
        with_summary = 0
        total = 0
        for (paper,) in session.execute(select(Paper)):
            total += 1
            if paper.pdf_path:
                with_pdf += 1
            if paper.sections and len(paper.sections) > 0:
                with_sections += 1
            if (paper.abstract and paper.abstract.strip()) and (
                paper.conclusion and paper.conclusion.strip()
            ):
                with_abs_concl += 1
            if paper.summary and paper.summary.strip():
                with_summary += 1
    typer.echo(
        json.dumps(
            {
                "total": total,
                "with_pdf": with_pdf,
                "with_sections": with_sections,
                "with_abstract_and_conclusion": with_abs_concl,
                "with_summary": with_summary,
            }
        )
    )


@app.command("ingest-pdf")
def cmd_ingest_pdf(
    url: str = typer.Option(..., "--url", help="Direct PDF URL"),
    title: str = typer.Option(..., "--title", help="Paper title"),
    source: str = typer.Option("dev", "--source", help="Source label to store"),
    license: str = typer.Option(
        "cc-by", "--license", help="Normalized license token (e.g., cc-by)"
    ),
    year: int | None = typer.Option(None, "--year"),
    authors: str = typer.Option("", "--authors", help="Comma-separated authors"),
):
    """Ingest a single PDF by URL, parse sections, and generate a summary.

    This is a convenience utility for demos and UI testing.
    """
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    ensure_storage_dir(settings.storage_dir)

    from .storage import download_pdf_to_storage

    pdf_path = download_pdf_to_storage(
        url, storage_dir=settings.storage_dir, file_hint=f"{source}-demo.pdf"
    )

    # Prefer configured backend if set to grobid; otherwise, use pdfminer
    sections: dict[str, str] = {}
    try:
        if settings.parser_backend == "grobid":
            sections = grobid_parse_pdf(pdf_path, host=settings.grobid_host)
            if not sections:
                sections = parse_pdf_into_sections(pdf_path)
        else:
            sections = parse_pdf_into_sections(pdf_path)
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"parse failed: {exc}", fg=typer.colors.RED)
        sections = {}

    abstract, conclusion = extract_abstract_and_conclusion(sections)
    summary = (
        summarize_sections(sections)
        if sections
        else (extractive_summary(abstract or "") if abstract else "")
    )

    from .models import Paper

    with session_factory() as session:
        paper = Paper(
            source=source,
            external_id=None,
            doi=None,
            title=title,
            authors={"list": [a.strip() for a in authors.split(",") if a.strip()]},
            abstract=abstract,
            license=license,
            pdf_path=pdf_path,
            sections=sections or {},
            conclusion=conclusion,
            summary=(summary[:1000] if summary else None),
            year=year,
            venue=None,
            concepts={"list": []},
            citation_count=None,
        )
        session.add(paper)
        session.commit()
        typer.echo(json.dumps({"ingested_id": paper.id, "has_sections": bool(sections)}))


@app.command("seed-demo-ui")
def cmd_seed_demo_ui():
    """Seed a demo paper with parsed sections and summary for UI testing.

    Creates or updates a paper with source="demo" and external_id="demo-1" so it can be
    discovered in `/search` and expanded in `/ui/search`.
    """
    from sqlalchemy import select

    from .models import Paper

    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)

    demo = {
        "title": "A Demo Transformer Study: Methods, Results and Conclusion",
        "authors": {"list": ["Demo Author"]},
        "abstract": "This demo paper showcases the UI pipeline.",
        "license": "cc-by",
        "year": 2024,
        "venue": "DemoConf",
        "citation_count": 123,
        "sections": {
            "Title": "A Demo Transformer Study: Methods, Results and Conclusion",
            "Abstract": "This demo paper showcases the UI pipeline for summaries and sections.",
            "Methods": "We used a simple heuristic-based approach.",
            "Results": "We observed consistent improvements in responsiveness.",
            "Conclusion": "The system enables quick understanding without opening PDFs.",
        },
        "conclusion": "The system enables quick understanding without opening PDFs.",
        "summary": "We describe a transformer-focused demo, outline the methods used, report results, and conclude with the system's benefits.",
    }

    with session_factory() as session:
        existing = session.execute(
            select(Paper).where(Paper.source == "demo", Paper.external_id == "demo-1")
        ).scalar_one_or_none()
        if existing is None:
            paper = Paper(
                source="demo",
                external_id="demo-1",
                doi=None,
                title=demo["title"],
                authors=demo["authors"],
                abstract=demo["abstract"],
                license=demo["license"],
                pdf_path=None,
                sections=demo["sections"],
                conclusion=demo["conclusion"],
                summary=demo["summary"],
                year=demo["year"],
                venue=demo["venue"],
                concepts={"list": ["demo"]},
                citation_count=demo["citation_count"],
            )
            session.add(paper)
            session.commit()
            pid = paper.id
        else:
            # Update fields in case of re-run
            existing.title = demo["title"]
            existing.authors = demo["authors"]
            existing.abstract = demo["abstract"]
            existing.license = demo["license"]
            existing.sections = demo["sections"]
            existing.conclusion = demo["conclusion"]
            existing.summary = demo["summary"]
            existing.year = demo["year"]
            existing.venue = demo["venue"]
            existing.concepts = {"list": ["demo"]}
            existing.citation_count = demo["citation_count"]
            session.add(existing)
            session.commit()
            pid = existing.id
    typer.echo(json.dumps({"seeded_id": pid}))


if __name__ == "__main__":
    app()
