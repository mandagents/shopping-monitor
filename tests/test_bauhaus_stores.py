"""Tests for bauhaus_stores source.

Unit tests cover the pure helpers ``parse_purchasability_json()`` and
``parse_price_from_html()`` — no browser is needed.

The browser integration test (``test_check_live``) is guarded by the
``BAUHAUS_BROWSER_TESTS`` env var and is skipped by default so the normal CI
suite stays fast and green without a browser.
"""
from __future__ import annotations

import os

import pytest

from src.sources.bauhaus_stores import parse_price_from_html, parse_purchasability_json


# ---------------------------------------------------------------------------
# Fixtures — purchasability JSON
# ---------------------------------------------------------------------------

_PURCHASABILITY_IN_STORE = {
    "results": [
        {"amount": 0, "code": "ONA", "kind": "ONLINE", "product": "31934233", "purchasable": False},
        {"amount": 1, "code": "SOS", "kind": "STORE", "product": "31934233", "purchasable": True},
    ]
}

_PURCHASABILITY_OUT_OF_STORE = {
    "results": [
        {"amount": 0, "code": "ONA", "kind": "ONLINE", "product": "31934233", "purchasable": False},
        {"amount": 0, "code": "SOOS", "kind": "STORE", "product": "31934233", "purchasable": False},
    ]
}

_PURCHASABILITY_ONLY_ONLINE = {
    "results": [
        {"amount": 1, "code": "ONA", "kind": "ONLINE", "product": "31934233", "purchasable": True},
    ]
}

_PURCHASABILITY_EMPTY_RESULTS = {"results": []}
_PURCHASABILITY_NO_RESULTS_KEY = {"foo": "bar"}
_PURCHASABILITY_RESULTS_NOT_LIST = {"results": "bad"}


# ---------------------------------------------------------------------------
# Fixtures — HTML with price
# ---------------------------------------------------------------------------

_HTML_WITH_JSONLD_PRICE = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Midea PortaSplit",
  "sku": "31934233",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "749.00",
    "availability": "https://schema.org/InStock"
  }
}
</script>
</body></html>
"""

_HTML_WITH_JSONLD_PRICE_COMMA = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Midea PortaSplit",
  "sku": "31934233",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "749,00"
  }
}
</script>
</body></html>
"""

_HTML_VISIBLE_PRICE_FALLBACK = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Midea PortaSplit",
  "sku": "31934233",
  "offers": {"@type": "Offer"}
}
</script>
<span>749,00 €</span>
</body></html>
"""

_HTML_NO_PRICE = """\
<html><body>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Product","name":"x","offers":{"@type":"Offer"}}
</script>
</body></html>
"""

_HTML_NO_PRODUCT_JSONLD = """\
<html><body>
<script type="application/ld+json">
{"@type": "BreadcrumbList", "itemListElement": []}
</script>
<span>749,00 €</span>
</body></html>
"""


# ---------------------------------------------------------------------------
# Unit tests — parse_purchasability_json() (pure, no browser)
# ---------------------------------------------------------------------------


def test_store_purchasable_true():
    assert parse_purchasability_json(_PURCHASABILITY_IN_STORE) is True


def test_store_purchasable_false():
    assert parse_purchasability_json(_PURCHASABILITY_OUT_OF_STORE) is False


def test_no_store_entry_returns_none():
    """Anti-silent-failure: no STORE kind entry → None."""
    assert parse_purchasability_json(_PURCHASABILITY_ONLY_ONLINE) is None


def test_empty_results_returns_none():
    assert parse_purchasability_json(_PURCHASABILITY_EMPTY_RESULTS) is None


def test_missing_results_key_returns_none():
    assert parse_purchasability_json(_PURCHASABILITY_NO_RESULTS_KEY) is None


def test_results_not_list_returns_none():
    assert parse_purchasability_json(_PURCHASABILITY_RESULTS_NOT_LIST) is None


def test_empty_dict_returns_none():
    assert parse_purchasability_json({}) is None


# ---------------------------------------------------------------------------
# Unit tests — parse_price_from_html() (pure, no browser)
# ---------------------------------------------------------------------------


def test_price_from_jsonld_dot():
    assert parse_price_from_html(_HTML_WITH_JSONLD_PRICE) == 749.0


def test_price_from_jsonld_comma():
    assert parse_price_from_html(_HTML_WITH_JSONLD_PRICE_COMMA) == 749.0


def test_price_from_visible_text_fallback():
    """Falls back to visible '749,00 €' when JSON-LD offer has no price."""
    assert parse_price_from_html(_HTML_VISIBLE_PRICE_FALLBACK) == 749.0


def test_no_price_returns_none():
    assert parse_price_from_html(_HTML_NO_PRICE) is None


def test_no_product_jsonld_falls_back_to_visible():
    """Non-Product JSON-LD blocks are skipped; visible price is found."""
    assert parse_price_from_html(_HTML_NO_PRODUCT_JSONLD) == 749.0


def test_empty_html_returns_none():
    assert parse_price_from_html("<html></html>") is None


# ---------------------------------------------------------------------------
# Registry smoke tests (no browser)
# ---------------------------------------------------------------------------


def test_bauhaus_stores_in_known_sources():
    from src.sources import KNOWN_SOURCES, get_check, unknown_sources

    assert "bauhaus_stores" in KNOWN_SOURCES
    assert unknown_sources(["bauhaus_stores"]) == []
    assert callable(get_check("bauhaus_stores"))


# ---------------------------------------------------------------------------
# Browser integration test — skipped unless BAUHAUS_BROWSER_TESTS=1
# ---------------------------------------------------------------------------

_BROWSER_REASON = (
    "Set BAUHAUS_BROWSER_TESTS=1 to run live Playwright integration test "
    "(requires network + chromium headless-shell)"
)


@pytest.mark.skipif(
    os.environ.get("BAUHAUS_BROWSER_TESTS") != "1",
    reason=_BROWSER_REASON,
)
def test_check_live():
    """Live browser test: runs check() for real and prints the resulting Offer."""
    from src.sources.bauhaus_stores import check

    offer = check(None)  # client is ignored

    print(f"\nLive Offer: {offer}")

    assert offer is not None, "check() returned None — page did not render or XHR not captured"
    assert offer.source == "bauhaus_stores"
    assert offer.ean == "4048164116478"
    assert "Hamburg-Moorfleet" in offer.title
    assert offer.pickup_only is True
    assert offer.url.startswith("https://www.bauhaus.info/")
    assert isinstance(offer.available, bool)
    if offer.price is not None:
        assert 100 < offer.price < 2000, f"Implausible price: {offer.price}"
