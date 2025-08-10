from __future__ import annotations

import pathlib
import shutil
from collections.abc import Generator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture()
def page(browser: Browser, request: pytest.FixtureRequest) -> Generator[Page, None, None]:
    artifacts_dir = pathlib.Path("artifacts/ui-e2e")
    video_dir = artifacts_dir / "video"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    context = browser.new_context(record_video_dir=str(video_dir))
    # Enable tracing to capture on failures
    context.tracing.start(screenshots=True, snapshots=True, sources=True)

    page = context.new_page()
    try:
        yield page
    finally:
        # Stop tracing and save only on failure
        rep_call = getattr(request.node, "rep_call", None)
        try:
            if rep_call and getattr(rep_call, "failed", False):
                trace_path = artifacts_dir / f"{request.node.name}-trace.zip"
                context.tracing.stop(path=str(trace_path))
            else:
                context.tracing.stop()
        except Exception:
            # Best-effort; avoid failing teardown on tracing errors
            pass

        # Close context to finalize video files
        try:
            context.close()
        finally:
            # Move video to a deterministic name if present
            try:
                if hasattr(page, "video") and page.video:
                    src = page.video.path()
                    if src:
                        dest = video_dir / f"{request.node.name}.webm"
                        shutil.move(str(src), str(dest))
            except Exception:
                pass


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    # Allow fixtures to inspect test outcome via request.node.rep_* attributes
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)
