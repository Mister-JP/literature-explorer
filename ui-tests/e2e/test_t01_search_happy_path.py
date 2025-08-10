from __future__ import annotations

import os
import pathlib

from playwright.sync_api import Page, expect


def test_t01_search_happy_path(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    url = f"{base_url}/ui/search?q=transformer"

    console_errors: list[str] = []

    def _on_console(msg) -> None:
        try:
            if msg.type == "error":
                console_errors.append(msg.text)
        except Exception:
            # Best-effort; ignore parsing issues
            pass

    page.on("console", _on_console)

    page.goto(url)

    meta = page.locator("#result-meta")
    expect(meta).to_be_visible()

    # Validate count, latency, sort via data-* attributes
    total_attr = meta.get_attribute("data-total") or "0"
    latency_attr = meta.get_attribute("data-latency") or ""
    sort_attr = meta.get_attribute("data-sort") or ""

    assert int(total_attr) > 0, f"Expected >0 results, got {total_attr}"
    assert latency_attr != "", "Expected latency to be present"
    assert sort_attr in {"recency", "citations"}, f"Unexpected sort: {sort_attr}"

    # At least one visible row
    rows = page.locator("tbody tr").filter(has=page.get_by_role("button", name="Details"))
    assert rows.count() > 0, "Expected at least one result row"

    # Full-page screenshot
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts_dir / "t01-search-happy.png"), full_page=True)

    # No console errors
    assert not console_errors, f"Console errors found: {console_errors}"
