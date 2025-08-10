from __future__ import annotations

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
def page(browser: Browser) -> Page:
    context = browser.new_context()
    try:
        page = context.new_page()
        yield page
    finally:
        context.close()
