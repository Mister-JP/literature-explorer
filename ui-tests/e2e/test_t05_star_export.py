from __future__ import annotations

import os
import pathlib

from playwright.sync_api import Page, expect


def _read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def test_t05_star_and_export(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    page.goto(f"{base_url}/ui/search?q=transformer")

    # Ensure at least one result row exists
    rows = page.locator("tbody tr").filter(has=page.get_by_role("button", name="Details"))
    expect(rows.first).to_be_visible()

    # Toggle star on the first row
    star_btn = page.locator("button.star").first
    item_id = star_btn.get_attribute("data-id")
    star_btn.click()
    expect(star_btn).to_have_text("★")
    expect(star_btn).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#star-count")).to_contain_text("Starred: 1")

    # Export visible (CSV)
    with page.expect_download() as dl_info:
        page.locator("#export-visible").click()
    dl = dl_info.value
    visible_csv = artifacts_dir / "t05-visible.csv"
    dl.save_as(str(visible_csv))
    txt = _read_text(visible_csv)
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    assert lines and lines[0].strip() == "id,title,year,citation_count,license,source,links"
    assert len(lines) >= 2, "expected at least one data row in visible export"

    # Export starred (CSV) and assert only the starred item is present
    with page.expect_download() as dl2_info:
        page.locator("#export-starred").click()
    dl2 = dl2_info.value
    starred_csv = artifacts_dir / "t05-starred.csv"
    dl2.save_as(str(starred_csv))
    txt2 = _read_text(starred_csv)
    lines2 = [ln for ln in txt2.splitlines() if ln.strip()]
    assert lines2 and lines2[0].strip() == "id,title,year,citation_count,license,source,links"
    assert len(lines2) == 2, f"expected exactly one starred row, got {len(lines2)-1}"
    # The first field in the data row should match the starred id (quoted)
    data_first_field = lines2[1].split(",")[0].strip().strip('"')
    assert data_first_field == (
        item_id or ""
    ), f"starred export id mismatch: {data_first_field} != {item_id}"
