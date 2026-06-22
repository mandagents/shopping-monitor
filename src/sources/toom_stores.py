"""toom Hamburg-Wandsbek store availability via headless Playwright.

toom is a client-side-rendered React app: availability and price are NOT in
the initial HTML that httpx sees.  This source uses Playwright to:

1. Set the Hamburg-Wandsbek market before navigation (via cookies — robust,
   no fragile UI clicking required).
2. Wait for the page to fully render.
3. Extract availability + price from the rendered JSON-LD <script> tag (the
   most reliable signal: it is always present once React hydrates, and it
   reflects the currently selected market).

Market selection:
- toom stores the selected market in two cookies on toom.de:
  ``market_id`` (integer) and ``market_name`` (string).
- Hamburg-Wandsbek is the only toom Baumarkt located in Hamburg city limits
  (id=3420, zip=22047).  We set these cookies before navigation; toom's React
  front-end reads them on hydration and displays that market's stock.

Anti-silent-failure guards:
- If the Product JSON-LD is absent after render → return None  (health-check).
- If ``availability`` is absent from the JSON-LD offer → return None.
- If the rendered page does not contain the expected market name → return None
  (cookie was not honoured — layout change guard).
- Exception in Playwright code propagates up → monitor marks source as failed.

Signature follows the uniform ``check(client) -> Offer | None`` interface;
``client`` (httpx.Client) is intentionally ignored.
"""
from __future__ import annotations

import json
import re

from ..models import Offer
from .playwright_base import playwright_page

NAME = "toom_stores"
URL = "https://toom.de/p/mobiles-klimageraet-portasplit-12000-btuh/9350668"
EAN = "4048164116478"

# Hamburg-Wandsbek is the only toom market in Hamburg city proper.
_HH_MARKET_ID = "3420"
_HH_MARKET_NAME = "Hamburg-Wandsbek"

_COOKIES: list[dict] = [
    {
        "name": "market_id",
        "value": _HH_MARKET_ID,
        "domain": "toom.de",
        "path": "/",
        "secure": True,
        "sameSite": "Lax",
    },
    {
        "name": "market_name",
        "value": _HH_MARKET_NAME,
        "domain": "toom.de",
        "path": "/",
        "secure": True,
        "sameSite": "Lax",
    },
]

_PRICE_RE = re.compile(r"(\d{2,4})[.,](\d{2})\s*€")

# Schema.org availability URIs that mean "available for purchase".
_IN_STOCK_STATES = frozenset(
    {
        "http://schema.org/InStock",
        "https://schema.org/InStock",
        "http://schema.org/LimitedAvailability",
        "https://schema.org/LimitedAvailability",
        "http://schema.org/PreOrder",
        "https://schema.org/PreOrder",
        "http://schema.org/InStoreOnly",
        "https://schema.org/InStoreOnly",
    }
)

# Schema.org states that mean "pickup only" (no home delivery).
_PICKUP_ONLY_STATES = frozenset(
    {
        "http://schema.org/InStoreOnly",
        "https://schema.org/InStoreOnly",
    }
)


def parse_rendered(html: str) -> tuple[bool | None, bool, float | None]:
    """Parse the Playwright-rendered HTML of the toom product page.

    Extracts availability and price from the Product JSON-LD that React
    injects after hydration.

    Args:
        html: the full rendered HTML string.

    Returns:
        ``(available, pickup_only, price)`` where ``available`` is ``None``
        when the JSON-LD product or offer is missing (anti-silent-failure).
        ``pickup_only`` defaults to ``False`` when ``available is None``.
        ``price`` is ``None`` when no price could be parsed.

    This function is pure (no I/O) so it can be unit-tested without a browser.
    """
    # --- Extract JSON-LD Product block ---
    product_data: dict | None = None
    ld_re = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in ld_re.finditer(html):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            product_data = data
            break

    if product_data is None:
        return None, False, None  # page did not render Product JSON-LD

    offer = product_data.get("offers")
    if not isinstance(offer, dict):
        return None, False, None  # no offer block

    availability = offer.get("availability")
    if not availability:
        return None, False, None  # availability absent — anti-silent-failure

    available = availability in _IN_STOCK_STATES
    pickup_only = availability in _PICKUP_ONLY_STATES

    # Price: prefer JSON-LD (authoritative for the rendered page).
    price: float | None = None
    raw_price = offer.get("price")
    if raw_price is not None:
        try:
            price = float(str(raw_price).replace(",", "."))
        except (ValueError, TypeError):
            price = None

    # Fallback to visible price regex (e.g. "739,00 €")
    if price is None:
        m = _PRICE_RE.search(html)
        if m:
            price = float(f"{m.group(1)}.{m.group(2)}")

    return available, pickup_only, price


def check(client) -> Offer | None:  # noqa: ANN001  (client is httpx.Client, ignored)
    """Check toom Hamburg-Wandsbek store availability using Playwright.

    Sets the market via cookies before navigation — no fragile UI interaction.
    Returns ``None`` if the page does not render expected markers (triggers
    health-check alert rather than silently reporting unavailable).

    Args:
        client: httpx.Client — not used by this source (Playwright handles I/O).

    Returns:
        An :class:`~src.models.Offer` reflecting Hamburg-Wandsbek stock, or
        ``None`` on render failure.
    """
    with playwright_page(cookies=_COOKIES) as page:
        page.goto(URL, wait_until="networkidle")

        # Anti-silent-failure: verify the correct market is active on the page.
        page_text = page.inner_text("body")
        if _HH_MARKET_NAME not in page_text:
            raise RuntimeError(
                f"toom_stores: expected market '{_HH_MARKET_NAME}' not found in "
                "rendered page — cookie was not honoured or page layout changed."
            )

        html = page.content()

    available, pickup_only, price = parse_rendered(html)

    if available is None:
        # JSON-LD Product missing after render — surface as health-check failure.
        return None

    return Offer(
        source=NAME,
        title=f"Midea PortaSplit — toom {_HH_MARKET_NAME} (Abholung)",
        url=URL,
        price=price,
        available=available,
        pickup_only=True,  # toom stores: pickup only
        ean=EAN,
    )
