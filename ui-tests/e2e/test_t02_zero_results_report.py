from __future__ import annotations

import os
from playwright.sync_api import Page, expect


def test_t02_zero_results_and_report(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

    # Navigate to a query that yields zero results
    page.goto(f"{base_url}/ui/search?q=thisshouldyieldzero")

    empty = page.locator("#empty-state")
    expect(empty).to_be_visible()

    # Verify 3 suggestions are rendered
    expect(empty.locator("li")).to_have_count(3)

    # Click "Report this search" and assert POST to /ui/report returns 200
    with page.expect_response(lambda r: r.url.endswith("/ui/report") and r.request.method == "POST" and r.ok):
        page.get_by_role("button", name="Report this search").click()

    # Navigate to a valid query and assert the empty state is gone
    page.goto(f"{base_url}/ui/search?q=transformer")
    expect(page.locator("#empty-state")).to_have_count(0)


