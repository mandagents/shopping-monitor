"""OBI Hamburg store-level (pickup) availability via OBI's JSON stock API.

API: GET https://www.obi.de/api/pdp/v1/stock/{SKU}?storeIds={comma-separated}
Response: list of {"storeId": "...", "availableQuantity": int, ...}

Anti-silent-failure guard: any deviation from the expected list-of-dicts-with-
availableQuantity structure raises ValueError so format changes surface as health
failures rather than false "not available" readings.
"""
from __future__ import annotations

from ..jsonld import extract_jsonld, find_product, first_offer, offer_price
from ..models import Offer
from .base import _UA

NAME = "obi_stores"
SKU = "8620890"
PRODUCT_URL = "https://www.obi.de/p/8620890/midea-mobile-split-klimaanlage-portasplit"
STOCK_API_URL = (
    "https://www.obi.de/api/pdp/v1/stock/8620890"
    "?storeIds=281,497,420,040,483,443,377,545,253,569"
)
EAN = "4048164116478"

# Hamburg-area OBI store IDs (Eppendorf, Altona, Norderstedt, Glinde,
# Bergedorf, Harburg, Neugraben, Buchholz, …)
_HH_STORE_IDS = ["281", "497", "420", "040", "483", "443", "377", "545", "253", "569"]


def parse_stock(stock_json: list[dict]) -> list[str]:
    """Parse the OBI stock API response and return a list of in-stock store IDs.

    Args:
        stock_json: the parsed JSON body from the stock API — must be a
            non-empty list of dicts each containing an ``availableQuantity`` key.

    Returns:
        List of storeId strings where availableQuantity > 0.

    Raises:
        ValueError: if stock_json is not a non-empty list of dicts with the
            expected ``availableQuantity`` key (format-change guard).
    """
    if not isinstance(stock_json, list) or len(stock_json) == 0:
        raise ValueError(
            f"OBI stock API: expected non-empty list, got {type(stock_json).__name__!r}"
            f" (len={len(stock_json) if isinstance(stock_json, list) else 'n/a'})"
        )
    for entry in stock_json:
        if not isinstance(entry, dict):
            raise ValueError(
                f"OBI stock API: list entry is not a dict: {entry!r}"
            )
        if "availableQuantity" not in entry:
            raise ValueError(
                f"OBI stock API: entry missing 'availableQuantity' key: {entry!r}"
            )
    return [
        str(entry["storeId"])
        for entry in stock_json
        if entry["availableQuantity"] > 0
    ]


def _get_price(client) -> float | None:
    """Best-effort price extraction from the OBI product page JSON-LD."""
    try:
        resp = client.get(
            PRODUCT_URL,
            headers={
                "User-Agent": _UA,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "de-DE,de;q=0.9",
            },
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
        product = find_product(extract_jsonld(resp.text))
        if product is None:
            return None
        offer = first_offer(product)
        if offer is None:
            return None
        return offer_price(offer, "offer")
    except Exception:
        return None


def check(client) -> Offer | None:
    """Check OBI Hamburg store-level pickup availability.

    Fetches the stock API (raises on HTTP error or malformed response),
    then fetches the product page for a best-effort price.

    Returns an Offer with pickup_only=True and the EAN set so filter.should_alert
    can match it by identity rather than title matching.
    """
    resp = client.get(
        STOCK_API_URL,
        headers={
            "User-Agent": _UA,
            "Accept": "application/json",
        },
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    stock_json = resp.json()

    # Guard: raises ValueError on malformed response (format-change detection)
    in_stock = parse_stock(stock_json)

    price = _get_price(client)

    store_count = len(in_stock)
    if store_count == 1:
        store_label = "1 Markt"
    else:
        store_label = f"{store_count} Märkte"

    return Offer(
        source=NAME,
        title=f"Midea PortaSplit — OBI Abholung Hamburg ({store_label})",
        url=PRODUCT_URL,
        price=price,
        available=store_count > 0,
        pickup_only=True,
        ean=EAN,
    )
