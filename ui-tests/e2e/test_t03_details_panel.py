from __future__ import annotations

import json
import os
import pathlib

from playwright.sync_api import Page, expect


def test_t03_details_panel_loads_and_fails_gracefully(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Happy path: sections load or empty message
    page.goto(f"{base_url}/ui/search?q=transformer")
    first_expand = page.locator("button.expand").first
    expect(first_expand).to_be_visible()
    item_id = first_expand.get_attribute("data-id")
    with page.expect_response(
        lambda r: r.url.endswith(f"/paper/{item_id}") and r.request.method == "GET"
    ):
        first_expand.click()
    sections = page.locator(f"#details-{item_id} .sections")
    expect(sections).to_be_visible()
    # Either sections render or an empty message appears
    # Prefer concrete signal: if any headers exist, accept as success; otherwise fallback text
    headers = sections.locator(".section h4")
    if headers.count() >= 1:
        pass
    else:
        expect(sections).to_contain_text("No parsed sections available.")
    page.screenshot(path=str(artifacts_dir / "t03-details-success.png"), full_page=True)

    # Failure path: force /paper/{id} to 500 and verify fallback UI and telemetry
    page.goto(f"{base_url}/ui/search?q=transformer")
    # Route /paper/* to return 500
    page.route("**/paper/*", lambda route: route.fulfill(status=500, body=json.dumps({})))

    # Capture api_error telemetry request
    def _is_api_error(req) -> bool:
        if not req.url.endswith("/ui/telemetry") or req.method != "POST":
            return False
        try:
            data = req.post_data or ""
            return '"event_type":"api_error"' in data
        except Exception:
            return False

    first_expand = page.locator("button.expand").first
    item_id = first_expand.get_attribute("data-id")
    with page.expect_request(_is_api_error):
        first_expand.click()
    sections = page.locator(f"#details-{item_id} .sections")
    expect(sections).to_be_visible()
    expect(sections).to_contain_text("Failed to load sections.")
    page.screenshot(path=str(artifacts_dir / "t03-details-failure.png"), full_page=True)
