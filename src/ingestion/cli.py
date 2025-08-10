from __future__ import annotations

import json

import typer
import yaml
from dotenv import load_dotenv

from .citations import fetch_openalex_neighbors
from .config import Settings
from .connectors.arxiv import ArxivConnector
from .connectors.base import QuerySpec
from .connectors.doaj import DOAJConnector
from .connectors.openalex import OpenAlexConnector
from .connectors.semanticscholar import SemanticScholarConnector
from .db import Base, create_session_factory, ensure_schema
from .ingest import ingest_records
from .storage import ensure_storage_dir


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
        "arxiv", "--source", help="Data source: arxiv|openalex|semanticscholar"
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
    source: str = typer.Option("arxiv", "--source"),
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
):
    """Fetch citation neighbors via OpenAlex and enqueue ingestion for discovered DOIs."""
    load_dotenv()
    settings = Settings.from_env()
    session_factory = create_session_factory(settings.database_url)
    _init_db(session_factory)
    ensure_storage_dir(settings.storage_dir)

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
                # Ingest by DOI using OpenAlex search (filter by DOI)
                connector = {
                    "arxiv": ArxivConnector(),
                    "openalex": OpenAlexConnector(),
                    "semanticscholar": SemanticScholarConnector(),
                    "doaj": DOAJConnector(),
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


if __name__ == "__main__":
    app()
