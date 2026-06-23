from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ProductConfig

from .models import Offer


def _name_match(offer: Offer, p: "ProductConfig") -> bool:
    """Return True if offer title satisfies the name-match rules of product p."""
    title = (offer.title or "").lower()
    if any(x.lower() in title for x in p.match_exclude_any):
        return False
    if not all(x.lower() in title for x in p.match_require_all):
        return False
    if not p.match_require_any:
        return True
    return any(x.lower() in title for x in p.match_require_any)


def matches_product(offer: Offer, p: "ProductConfig") -> bool:
    """Return True if offer matches a single ProductConfig (back-compat helper).

    Matching rules:
    - If offer has an EAN *and* p has a non-empty EAN  → EAN equality wins.
    - Otherwise → name-match (require_all / require_any / exclude_any).
    """
    if offer.ean and p.ean:
        return offer.ean == p.ean
    return _name_match(offer, p)


def match_product(offer: Offer, products: list) -> "ProductConfig | None":
    """Return the first ProductConfig from *products* that this offer matches.

    Matching rules per product:
    - If offer.ean is set *and* product.ean is non-empty → match iff equal.
    - Otherwise (offer has no EAN, or product has no EAN) → name-match.

    Returns None if no product matches.
    """
    for p in products:
        if offer.ean and p.ean:
            # Both have EAN: strict equality, no name-match fallback.
            if offer.ean == p.ean:
                return p
        else:
            # At least one side lacks an EAN: use name-match.
            if _name_match(offer, p):
                return p
    return None


def should_alert(offer: Offer, products: list) -> bool:
    """Return True iff the offer should trigger an alert.

    - Finds the matching product via match_product().
    - Checks availability, non-None price, and per-product price cap.
    """
    p = match_product(offer, products)
    if p is None:
        return False
    if not offer.available:
        return False
    if offer.price is None or offer.price > p.max_price_eur:
        return False
    return True
