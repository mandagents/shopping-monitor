"""Shared Playwright helper for headless-browser sources.

Usage::

    with playwright_page(cookies=[...]) as page:
        page.goto(url, ...)
        ...

A realistic User-Agent and a 30 s default navigation timeout are pre-configured.
Chromium headless-shell is used (smaller, faster than full Chromium).
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Page, sync_playwright

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_DEFAULT_TIMEOUT_MS = 30_000  # navigation timeout


@contextmanager
def playwright_page(
    cookies: list[dict] | None = None,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> Iterator[Page]:
    """Context manager that yields a ready-to-use Playwright Page.

    Args:
        cookies: optional list of cookie dicts (name/value/domain/path/…) to
            inject into the browser context before any navigation.
        timeout_ms: default navigation timeout in milliseconds.

    Yields:
        A Playwright :class:`Page` instance.  The browser is closed on exit.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=_UA)
            context.set_default_navigation_timeout(timeout_ms)
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            yield page
        finally:
            browser.close()
