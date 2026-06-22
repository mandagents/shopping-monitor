"""BAUHAUS Hamburg-Moorfleet Fachcentrum availability via headless Playwright.

BAUHAUS is Cloudflare-protected: plain httpx gets HTTP 403.  A real Playwright
browser bypasses Cloudflare (HTTP 200, full page renders).

Strategy
--------
1. Pre-set the Hamburg-Moorfleet Fachcentrum via two cookies before navigation
   (``selectedStore`` JSON-encoded + ``favoriteFachcentrum`` = "595").  This is
   identical to what the BAUHAUS front-end writes when a user clicks a store.
2. Navigate to the product page (``domcontentloaded``).  BAUHAUS's own front-end
   then fetches ``/api/purchasability?productId=...&storeId=595`` automatically.
3. Intercept that XHR response via Playwright's ``on("response", …)`` handler —
   the page's native fetch includes all required CSRF/session headers so the API
   returns HTTP 200.  Our manual ``page.request.get`` gets 403 because it lacks
   those internal headers; therefore interception is the correct approach.
4. Parse the JSON: ``results[].kind == "STORE"`` entry's ``purchasable`` field is
   the authoritative in-store pickup availability flag.
5. Extract price from the Product JSON-LD block (always present in the rendered
   HTML once the page loads).

Anti-silent-failure guards
--------------------------
- If Cloudflare challenges (page title contains "Sicherheitsprüfung" / "Just a
  moment") → raise ``RuntimeError``.
- If the page does not confirm the Hamburg-Moorfleet store name → raise
  ``RuntimeError`` (cookie not honoured / layout changed).
- If the purchasability XHR is never fired or its JSON lacks a STORE entry →
  return ``None`` (health-check alert).
- If ``purchasable`` key is absent → return ``None``.
- NEVER guess availability.

Signature follows the uniform ``check(client) -> Offer | None`` interface;
``client`` (httpx.Client) is intentionally ignored.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from ..models import Offer
from .playwright_base import playwright_page

NAME = "bauhaus_stores"
URL = "https://www.bauhaus.info/klimaanlagen/midea-klimasplitgeraet-portasplit-12000-btu/p/31934233"
EAN = "4048164116478"

# Hamburg-Moorfleet is the closest BAUHAUS Fachcentrum within Hamburg city proper.
# Store ID discovered from /fachcentren (URL path: hamburg-moorfleet/fc/595).
_HH_FC_ID = "595"
_HH_FC_NAME = "Hamburg-Moorfleet"

# BAUHAUS stores the selected store in two cookies:
#   selectedStore  — URL-encoded JSON with id/name/address/coordinates
#   favoriteFachcentrum — bare integer id string
_HH_FC_COOKIE_JSON = urllib.parse.quote(
    json.dumps(
        {
            "id": _HH_FC_ID,
            "name": _HH_FC_NAME,
            "address": "",
            "coordinates": {"lat": 53.5, "lon": 10.1},
        }
    )
)

_COOKIES: list[dict] = [
    {
        "name": "selectedStore",
        "value": _HH_FC_COOKIE_JSON,
        "domain": "www.bauhaus.info",
        "path": "/",
        "secure": True,
        "sameSite": "Lax",
    },
    {
        "name": "favoriteFachcentrum",
        "value": _HH_FC_ID,
        "domain": "www.bauhaus.info",
        "path": "/",
        "secure": True,
        "sameSite": "Lax",
    },
]

_PRICE_RE = re.compile(r"(\d{2,4})[.,](\d{2})\s*€")


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable, no browser I/O)
# ---------------------------------------------------------------------------


def parse_purchasability_json(data: dict) -> bool | None:
    """Parse the ``/api/purchasability`` response for in-store pickup status.

    Args:
        data: parsed JSON dict from the purchasability API.

    Returns:
        ``True`` if the STORE entry reports ``purchasable=True``,
        ``False`` if ``purchasable=False``, or ``None`` if the expected
        structure is absent (anti-silent-failure).
    """
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return None
    for entry in results:
        if isinstance(entry, dict) and entry.get("kind") == "STORE":
            purchasable = entry.get("purchasable")
            if isinstance(purchasable, bool):
                return purchasable
    return None  # no STORE entry found


def parse_price_from_html(html: str) -> float | None:
    """Extract price from the rendered BAUHAUS product page HTML.

    Prefers the Product JSON-LD ``offers.price`` field; falls back to the
    first visible price pattern (e.g. ``749,00 €``) in the HTML.

    Args:
        html: full rendered HTML string.

    Returns:
        Price as float, or ``None`` if not found.
    """
    # --- JSON-LD: most reliable ---
    ld_re = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in ld_re.finditer(html):
        try:
            block = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(block, dict) or block.get("@type") != "Product":
            continue
        offers = block.get("offers")
        if isinstance(offers, dict):
            raw = offers.get("price")
            if raw is not None:
                try:
                    return float(str(raw).replace(",", "."))
                except (ValueError, TypeError):
                    pass
        break  # only first Product block

    # --- Fallback: visible price text ---
    m = _PRICE_RE.search(html)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")

    return None


# ---------------------------------------------------------------------------
# Main check() function
# ---------------------------------------------------------------------------


def check(client) -> Offer | None:  # noqa: ANN001  (client is httpx.Client, ignored)
    """Check BAUHAUS Hamburg-Moorfleet availability using Playwright.

    Pre-sets the Hamburg-Moorfleet Fachcentrum cookie before navigation so
    BAUHAUS's front-end loads the correct store's availability automatically.
    Intercepts the purchasability XHR (200 OK) to read availability as JSON.
    Extracts price from the Product JSON-LD in the rendered HTML.

    Returns ``None`` on any structural failure (triggers health-check alert).
    Raises ``RuntimeError`` on Cloudflare block or missing store confirmation.

    Args:
        client: httpx.Client — not used (Playwright handles all I/O).

    Returns:
        An :class:`~src.models.Offer` for Hamburg-Moorfleet, or ``None``.
    """
    captured: dict = {}  # populated by XHR interception

    def _on_response(resp) -> None:
        url = resp.url
        if (
            "purchasability" in url
            and f"storeId={_HH_FC_ID}" in url
            and "productId=31934233" in url
            and "data" not in captured  # only capture first match
        ):
            try:
                captured["data"] = resp.json()
            except Exception as exc:
                captured["error"] = str(exc)

    with playwright_page(cookies=_COOKIES) as page:
        page.on("response", _on_response)

        page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
        # Allow XHR requests (purchasability etc.) time to complete.
        page.wait_for_timeout(6_000)

        # --- Anti-silent-failure: Cloudflare challenge check ---
        title = page.title()
        if any(phrase in title for phrase in ("Just a moment", "Sicherheitsprüfung", "403")):
            raise RuntimeError(
                f"bauhaus_stores: Cloudflare challenge page detected (title={title!r}). "
                "Playwright bypass failed."
            )

        # --- Anti-silent-failure: correct store confirmed in page ---
        page_text = page.inner_text("body")
        if _HH_FC_NAME not in page_text:
            raise RuntimeError(
                f"bauhaus_stores: expected Fachcentrum '{_HH_FC_NAME}' not found in "
                "rendered page — selectedStore cookie not honoured or layout changed."
            )

        html = page.content()

    # --- Parse purchasability (intercepted from page's own XHR) ---
    if "data" not in captured:
        # XHR was never fired — page structure changed or intercept missed.
        return None

    available = parse_purchasability_json(captured["data"])
    if available is None:
        # No STORE entry in purchasability response — anti-silent-failure.
        return None

    # --- Extract price ---
    price = parse_price_from_html(html)

    return Offer(
        source=NAME,
        title=f"Midea PortaSplit — BAUHAUS {_HH_FC_NAME} (Abholung)",
        url=URL,
        price=price,
        available=available,
        pickup_only=True,
        ean=EAN,
    )
