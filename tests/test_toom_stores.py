"""Tests for toom_stores source.

Unit tests cover the pure ``parse_rendered()`` helper — no browser needed.
The browser integration test (``test_check_live``) is guarded by the
``TOOM_BROWSER_TESTS`` env var and is skipped by default so the normal CI
suite stays fast and green without a browser.
"""
import os

import pytest

from src.sources.toom_stores import parse_rendered

# ---------------------------------------------------------------------------
# Minimal HTML fixtures
# ---------------------------------------------------------------------------

_PRODUCT_JSONLD_OUTOFSTOCK = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "sku": "9350668",
  "name": "Midea PortaSplit 12000 BTU/h",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "799",
    "availability": "http://schema.org/OutOfStock"
  }
}
</script>
<p>Mein Markt: Hamburg-Wandsbek</p>
</body></html>
"""

_PRODUCT_JSONLD_INSTOCK = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "sku": "9350668",
  "name": "Midea PortaSplit 12000 BTU/h",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "739",
    "availability": "http://schema.org/InStoreOnly"
  }
}
</script>
<p>Mein Markt: Hamburg-Wandsbek</p>
</body></html>
"""

_PRODUCT_JSONLD_HOMEDELIVERY = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "sku": "9350668",
  "name": "Midea PortaSplit 12000 BTU/h",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "739.00",
    "availability": "http://schema.org/InStock"
  }
}
</script>
</body></html>
"""

_NO_PRODUCT_JSONLD = """\
<html><body>
<script type="application/ld+json">
{"@type": "BreadcrumbList", "itemListElement": []}
</script>
</body></html>
"""

_MISSING_AVAILABILITY = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Midea PortaSplit",
  "offers": {"@type": "Offer", "price": "799"}
}
</script>
</body></html>
"""

_VISIBLE_PRICE_FALLBACK = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "Product",
  "name": "Midea PortaSplit",
  "offers": {
    "@type": "Offer",
    "availability": "http://schema.org/InStock"
  }
}
</script>
<span>739,00 €</span>
</body></html>
"""


# ---------------------------------------------------------------------------
# Unit tests — parse_rendered() (pure, no browser)
# ---------------------------------------------------------------------------

def test_outofstock_returns_false():
    available, pickup_only, price = parse_rendered(_PRODUCT_JSONLD_OUTOFSTOCK)
    assert available is False
    assert pickup_only is False
    assert price == 799.0


def test_instoreonly_is_available_and_pickup_only():
    available, pickup_only, price = parse_rendered(_PRODUCT_JSONLD_INSTOCK)
    assert available is True
    assert pickup_only is True
    assert price == 739.0


def test_instock_for_home_delivery():
    available, pickup_only, price = parse_rendered(_PRODUCT_JSONLD_HOMEDELIVERY)
    assert available is True
    assert pickup_only is False
    assert price == 739.0


def test_no_product_jsonld_returns_none_available():
    """Anti-silent-failure: missing Product JSON-LD → available=None."""
    available, pickup_only, price = parse_rendered(_NO_PRODUCT_JSONLD)
    assert available is None


def test_missing_availability_returns_none_available():
    """Anti-silent-failure: offer without availability key → available=None."""
    available, pickup_only, price = parse_rendered(_MISSING_AVAILABILITY)
    assert available is None


def test_empty_html_returns_none_available():
    available, pickup_only, price = parse_rendered("<html></html>")
    assert available is None


def test_visible_price_fallback_when_no_jsonld_price():
    """If JSON-LD has no price, fall back to the first visible '999,99 €' in HTML."""
    available, pickup_only, price = parse_rendered(_VISIBLE_PRICE_FALLBACK)
    assert available is True
    assert price == 739.0


def test_no_price_returns_none_price():
    """If neither JSON-LD nor visible price present, price is None."""
    html = """\
<html><body>
<script type="application/ld+json">
{"@context":"https://schema.org/","@type":"Product","name":"x",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStock"}}
</script>
</body></html>"""
    available, pickup_only, price = parse_rendered(html)
    assert available is True
    assert price is None


# ---------------------------------------------------------------------------
# Test that the sources registry knows about toom_stores
# ---------------------------------------------------------------------------

def test_toom_stores_in_known_sources():
    from src.sources import KNOWN_SOURCES, get_check, unknown_sources

    assert "toom_stores" in KNOWN_SOURCES
    assert unknown_sources(["toom_stores"]) == []
    assert callable(get_check("toom_stores"))


# ---------------------------------------------------------------------------
# Browser integration test — skipped unless TOOM_BROWSER_TESTS=1
# ---------------------------------------------------------------------------

_BROWSER_REASON = (
    "Set TOOM_BROWSER_TESTS=1 to run live Playwright integration test "
    "(requires network + chromium headless-shell)"
)


@pytest.mark.skipif(
    os.environ.get("TOOM_BROWSER_TESTS") != "1",
    reason=_BROWSER_REASON,
)
def test_check_live():
    """Live browser test: runs check() for real and prints the resulting Offer."""
    from src.sources.toom_stores import check

    offer = check(None)  # client is ignored

    print(f"\nLive Offer: {offer}")

    # Basic shape assertions (not availability — stock changes)
    assert offer is not None, "check() returned None — page did not render"
    assert offer.source == "toom_stores"
    assert offer.ean == "4048164116478"
    assert "Hamburg-Wandsbek" in offer.title
    assert offer.pickup_only is True
    assert offer.url.startswith("https://toom.de/")
    assert isinstance(offer.available, bool)
    # Price should be in a plausible range or None
    if offer.price is not None:
        assert 100 < offer.price < 2000, f"Implausible price: {offer.price}"
