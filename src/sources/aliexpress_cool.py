"""AliExpress availability check for Midea PortaSplit Cool 2,35 kW (de-DE locale).

Mirrors aliexpress.py in structure but targets item 1005012383386980
("MIDEA® PortaSplit Cool 2,35 kW …").  No reliable EAN is available for this
variant, so ean=None — the Offer will name-match the Cool product via
match_require_all=["portasplit","cool"] / match_require_any=["2,35","2.35","2350"].

Reuses all pure parsing helpers from aliexpress.py (no duplication).

Price extraction strategy
--------------------------
AliExpress's modern item pages include JSON-LD with availability but omit the
price from the LD block.  The sale price appears prominently early in the page
text as "696,70€" followed by "X,YY€ sparen".  We extract the first EUR price
from the page text that appears before the word "sparen" — this is the actual
sale/current price, not a recommendation-widget price.

Anti-silent-failure: if neither the JSON-LD nor the page-text heuristic yields
a plausible price, we return None so the health-check counter fires rather than
sending an alert without a verified price.
"""
from __future__ import annotations

import re

from ..jsonld import availability_state, extract_jsonld, find_product, first_offer
from ..models import Offer
from .aliexpress import (
    is_bot_challenge,
    is_unavailable,
    parse_embedded_data,
)
from .playwright_base import playwright_page

NAME = "aliexpress_cool"
ITEM_ID = "1005012383386980"
URL = f"https://de.aliexpress.com/item/{ITEM_ID}.html"
# No reliable EAN for the Cool variant — name-match handles product routing.
EAN = None
TITLE = "Midea PortaSplit Cool 2,35 kW — AliExpress (Versand DE)"

# Matches prices like "696,70" or "569.00" (2-4 digit integer + 2 decimal)
_PRICE_RE = re.compile(r"(\d{2,4})[,.](\d{2})€")


def _extract_page_text_price(page_text: str) -> float | None:
    """Extract the sale price from visible page text.

    AliExpress renders the current sale price first, followed immediately by
    the savings amount ("X sparen").  We extract the first EUR price that
    appears before "sparen" in the page text.  Prices < 50 or > 5000 are
    rejected as implausible.

    Args:
        page_text: the full visible text of the page (preserving newlines is OK).

    Returns:
        A float price, or None if no plausible price is found.
    """
    # Narrow to the portion before "sparen" to avoid recommendation-widget prices
    sparen_pos = page_text.lower().find("sparen")
    search_area = page_text[:sparen_pos] if sparen_pos > 0 else page_text[:2000]
    for m in _PRICE_RE.finditer(search_area):
        integer_part = int(m.group(1))
        decimal_part = int(m.group(2))
        price = integer_part + decimal_part / 100.0
        if 50 < price < 5000:
            return price
    return None


def check(client) -> Offer | None:  # noqa: ANN001  (client is httpx.Client, ignored)
    """Check AliExpress Cool 2,35 kW item availability using Playwright.

    Decision tree:
    1. Bot-challenge detected              → None  (health-check, not crash)
    2. Unavailable marker in page text     → Offer(available=False)
    3. JSON-LD InStock + price extracted   → Offer(available=True, price=<float>)
    4. Fallback: parse_embedded_data()     → Offer(available=True, price=<float>)
    5. No price found                      → None  (health-check, not false-positive)

    Args:
        client: httpx.Client — not used (Playwright handles all I/O).

    Returns:
        An :class:`~src.models.Offer` or None on failure / challenge.
    """
    with playwright_page(timeout_ms=45_000) as page:
        page.set_extra_http_headers({"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
        page.goto(URL, wait_until="networkidle")

        final_url = page.url
        page_text = page.inner_text("body")
        page_text_lower = page_text.lower()
        html = page.content()

    # --- Step 1: bot-challenge check ---
    if is_bot_challenge(final_url, page_text_lower):
        return None

    # --- Step 2: unavailability check ---
    if is_unavailable(page_text_lower):
        return Offer(
            source=NAME,
            title=TITLE,
            url=URL,
            price=None,
            available=False,
            pickup_only=False,
            ean=EAN,
        )

    # --- Step 3: try JSON-LD for availability + page-text for price ---
    jsonld_blocks = extract_jsonld(html)
    product_block = find_product(jsonld_blocks)
    jsonld_available: bool | None = None
    if product_block is not None:
        offer_block = first_offer(product_block)
        if offer_block is not None:
            availability = offer_block.get("availability")
            if availability is not None:
                jsonld_available, _ = availability_state(availability)

    # Try to get price from page text first (most reliable for AliExpress)
    price = _extract_page_text_price(page_text)

    # Fallback to embedded JS data blobs (legacy AliExpress pattern)
    if price is None:
        price = parse_embedded_data(html)

    if price is None:
        # Cannot confirm price — anti-silent-failure guard.
        return None

    # Determine availability: prefer JSON-LD signal, fall back to price-present heuristic
    available = jsonld_available if jsonld_available is not None else True

    return Offer(
        source=NAME,
        title=TITLE,
        url=URL,
        price=price,
        available=available,
        pickup_only=False,
        ean=EAN,
    )
