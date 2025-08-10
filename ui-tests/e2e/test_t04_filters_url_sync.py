from __future__ import annotations

import os
import pathlib
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import Page, expect


def test_t04_filters_and_url_sync(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Open seeded query
    page.goto(f"{base_url}/ui/search?q=transformer")

    # Set filters: source=arxiv (may zero results), license=cc-by, venue=DemoConf, year range, has_summary
    page.select_option("select[name=source]", "arxiv")
    page.select_option("select[name=license]", "cc-by")
    page.fill("input[name=venue]", "DemoConf")
    page.fill("input[name=year_start]", "2023")
    page.fill("input[name=year_end]", "2025")
    cb = page.locator("input[name=has_summary]")
    if not cb.is_checked():
        cb.check()

    # Submit
    page.get_by_role("button", name="Search").click()

    # Assert URL reflects filters
    parsed = urlparse(page.url)
    qs = parse_qs(parsed.query)
    assert qs.get("source", [""])[0] == "arxiv"
    assert qs.get("license", [""])[0] == "cc-by"
    assert qs.get("venue", [""])[0] == "DemoConf"
    assert qs.get("year_start", [""])[0] == "2023"
    assert qs.get("year_end", [""])[0] == "2025"
    assert qs.get("has_summary", [""])[0] == "1"

    # Results update to either rows or empty state
    rows = page.locator("tbody tr").filter(has=page.get_by_role("button", name="Details"))
    empty = page.locator("#empty-state")
    expect(rows.or_(empty)).to_be_visible()

    # Hard refresh preserves state
    page.reload()
    expect(page.locator("select[name=source]")).to_have_value("arxiv")
    expect(page.locator("select[name=license]")).to_have_value("cc-by")
    expect(page.locator("input[name=venue]")).to_have_value("DemoConf")
    expect(page.locator("input[name=year_start]")).to_have_value("2023")
    expect(page.locator("input[name=year_end]")).to_have_value("2025")
    expect(page.locator("input[name=has_summary]")).to_be_checked()

    # Copying the URL reproduces state
    url_copy = page.url
    page.goto(f"{base_url}/ui/search?q=transformer")
    page.goto(url_copy)
    expect(page.locator("select[name=source]")).to_have_value("arxiv")

    # Artifact: screenshot of filtered view
    page.screenshot(path=str(artifacts_dir / "t04-filters.png"), full_page=True)


