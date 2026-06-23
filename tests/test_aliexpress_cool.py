"""Tests for the AliExpress Cool 2,35 kW source.

Unit tests cover the registry + module constants.
The live browser integration test is guarded by ``ALIEXPRESS_COOL_BROWSER_TESTS=1``
so ``.venv/bin/python -m pytest -q`` stays green without a browser or network.
"""
from __future__ import annotations

import os

import pytest

from src.sources.aliexpress_cool import EAN, ITEM_ID, NAME, TITLE, URL


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

def test_name():
    assert NAME == "aliexpress_cool"


def test_item_id():
    assert ITEM_ID == "1005012383386980"


def test_url_contains_item_id():
    assert ITEM_ID in URL
    assert URL.startswith("https://de.aliexpress.com/item/")


def test_ean_is_none():
    """Cool variant has no reliable EAN — name-match handles routing."""
    assert EAN is None


def test_title_contains_portasplit_cool_and_kw():
    """Title must satisfy Cool product name-match rules:
    require_all=["portasplit","cool"], require_any=["2,35","2.35","2350"].
    """
    title_lower = TITLE.lower()
    assert "portasplit" in title_lower
    assert "cool" in title_lower
    assert "2,35" in title_lower


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_aliexpress_cool_in_known_sources():
    from src.sources import KNOWN_SOURCES, get_check, unknown_sources

    assert "aliexpress_cool" in KNOWN_SOURCES
    assert unknown_sources(["aliexpress_cool"]) == []
    fn = get_check("aliexpress_cool")
    assert callable(fn)


def test_get_check_returns_cool_check():
    from src.sources import get_check
    from src.sources.aliexpress_cool import check

    assert get_check("aliexpress_cool") is check


# ---------------------------------------------------------------------------
# Title satisfies Cool product name-match (filter integration)
# ---------------------------------------------------------------------------

def test_cool_title_matches_cool_product():
    from src.config import ProductConfig
    from src.filter import match_product, matches_product
    from src.models import Offer

    cool_product = ProductConfig(
        name="Midea PortaSplit Cool 2,35 kW",
        ean="",
        model_no="",
        max_price_eur=850.0,
        match_require_all=["portasplit", "cool"],
        match_require_any=["2,35", "2.35", "2350"],
        match_exclude_any=[],
    )
    product_35 = ProductConfig(
        name="Midea PortaSplit 3,5 kW (Wärmepumpe)",
        ean="4048164116478",
        model_no="10002085",
        max_price_eur=850.0,
        match_require_all=["portasplit"],
        match_require_any=["12000", "12.000", "3,5", "3.5"],
        match_exclude_any=["cool", "2,35", "2.35"],
    )
    products = [product_35, cool_product]

    # Simulate the offer aliexpress_cool.check() produces when available
    offer = Offer(
        source=NAME,
        title=TITLE,
        url=URL,
        price=699.0,
        available=True,
        pickup_only=False,
        ean=EAN,  # None
    )

    # Must NOT match 3,5 kW (excluded by "cool" in exclude_any)
    assert matches_product(offer, product_35) is False

    # Must match Cool product
    assert matches_product(offer, cool_product) is True

    # match_product must return cool_product, NOT product_35
    result = match_product(offer, products)
    assert result is cool_product


# ---------------------------------------------------------------------------
# Live browser integration test — skipped unless ALIEXPRESS_COOL_BROWSER_TESTS=1
# ---------------------------------------------------------------------------

_BROWSER_REASON = (
    "Set ALIEXPRESS_COOL_BROWSER_TESTS=1 to run the live Playwright integration "
    "test (requires network + chromium headless-shell; AliExpress may block "
    "datacenter IPs with a bot-challenge — that returns None, not a failure)."
)


@pytest.mark.skipif(
    os.environ.get("ALIEXPRESS_COOL_BROWSER_TESTS") != "1",
    reason=_BROWSER_REASON,
)
def test_check_live():
    """Live browser test: run check() for the Cool 2,35 kW item and assert shape.

    Prints the Offer so callers can paste it into the verification report.
    """
    from src.sources.aliexpress_cool import check

    offer = check(None)

    print(f"\nLive Offer (Cool): {offer}")

    assert offer is not None, (
        "check() returned None — AliExpress challenged the headless browser "
        "(bot-protection / slider / punish page).  CI IP-block risk is real."
    )

    assert offer.source == NAME
    assert offer.ean is None
    assert offer.url == URL
    assert offer.pickup_only is False
    assert "portasplit" in offer.title.lower()
    assert "cool" in offer.title.lower()
    assert "2,35" in offer.title.lower()
    assert isinstance(offer.available, bool)

    if offer.available:
        assert offer.price is not None
        assert 50 < offer.price < 2000, f"Implausible price: {offer.price}"
