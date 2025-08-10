from __future__ import annotations

import os
import pathlib

from playwright.sync_api import Page, expect


def test_t02_zero_results_and_report(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Navigate to a query that yields zero results
    page.goto(f"{base_url}/ui/search?q=thisshouldyieldzero")

    empty = page.locator("#empty-state")
    expect(empty).to_be_visible()

    # Verify 3 suggestions are rendered
    expect(empty.locator("li")).to_have_count(3)

    # Capture screenshot of the empty state
    page.screenshot(path=str(artifacts_dir / "t02-zero-state.png"), full_page=True)

    # Click "Report this search" and assert POST to /ui/report returns 200, then save response
    with page.expect_response(
        lambda r: r.url.endswith("/ui/report") and r.request.method == "POST"
    ) as resp_info:
        page.get_by_role("button", name="Report this search").click()
    resp = resp_info.value
    assert resp.ok, f"/ui/report failed: {resp.status}"
    try:
        body = resp.text()
    except Exception:
        body = ""
    (artifacts_dir / "t02-report-response.txt").write_text(
        f"status={resp.status}\nbody={body}\n", encoding="utf-8"
    )

    # Navigate to a valid query and assert the empty state is gone; capture screenshot
    page.goto(f"{base_url}/ui/search?q=transformer")
    expect(page.locator("#empty-state")).to_have_count(0)
    page.screenshot(path=str(artifacts_dir / "t02-valid-query.png"), full_page=True)
