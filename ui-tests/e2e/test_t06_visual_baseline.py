from __future__ import annotations

import os
import pathlib
from PIL import Image, ImageChops
from playwright.sync_api import Page


def _ensure_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def test_t06_visual_baseline(page: Page) -> None:
    base_url = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    baseline_dir = pathlib.Path("ui-tests/snapshots")
    _ensure_dir(artifacts_dir)
    _ensure_dir(baseline_dir)

    # Capture current screenshot
    url = f"{base_url}/ui/search?q=transformer"
    page.goto(url)
    current_path = artifacts_dir / "t06-current.png"
    page.screenshot(path=str(current_path), full_page=True)

    # Baseline handling
    baseline_path = baseline_dir / "t06-search-baseline.png"
    if not baseline_path.exists():
        # Establish baseline on first run
        baseline_path.write_bytes(current_path.read_bytes())
        return

    # Compare with baseline
    with Image.open(baseline_path).convert("RGBA") as img_base, Image.open(current_path).convert(
        "RGBA"
    ) as img_cur:
        # Resize to the smallest common size to avoid DPI/noise mismatch causing exceptions
        w = min(img_base.width, img_cur.width)
        h = min(img_base.height, img_cur.height)
        if img_base.size != (w, h):
            img_base = img_base.resize((w, h))
        if img_cur.size != (w, h):
            img_cur = img_cur.resize((w, h))
        diff = ImageChops.difference(img_base, img_cur)
        bbox = diff.getbbox()
        if bbox is None:
            # No diff
            return
        # Save diff artifact and fail
        diff_path = artifacts_dir / "t06-diff.png"
        diff.save(diff_path)
        # Also copy baseline for convenience
        (artifacts_dir / "t06-baseline.png").write_bytes(baseline_path.read_bytes())
        raise AssertionError(
            "Visual diff detected. Review artifacts/ui-e2e/t06-diff.png and update baseline if intended."
        )


