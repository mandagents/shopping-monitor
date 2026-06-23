"""Tests for hornbach source.

Unit tests cover the pure helpers ``parse_availability_signals()`` and
``parse_price_from_html()`` — no browser is needed.

The browser integration test (``test_check_live``) is guarded by the
``HORNBACH_BROWSER_TESTS`` env var and is skipped by default so the normal CI
suite stays fast and green without a browser.
"""
from __future__ import annotations

import os

import pytest

from src.sources.hornbach import parse_availability_signals, parse_price_from_html


# ---------------------------------------------------------------------------
# Fixtures — body text
# ---------------------------------------------------------------------------

_TEXT_NEITHER_ONLINE_NOR_STORE = "Preis: 749,00 €. Art.-Nr. 12356554."

_TEXT_ONLINE_NOT_ORDERABLE_STORE_NOT_AVAILABLE = """\
Z.ZT. NICHT ONLINE BESTELLBAR
HORNBACH Hamburg
Z.Zt. nicht im Markt vorrätig
"""

_TEXT_ONLINE_NOT_ORDERABLE_STORE_AVAILABLE = """\
Z.ZT. NICHT ONLINE BESTELLBAR
HORNBACH Hamburg
im Markt vorrätig
"""

_TEXT_ONLINE_ORDERABLE_STORE_NOT_AVAILABLE = """\
online bestellbar
HORNBACH Hamburg
Z.Zt. nicht im Markt vorrätig
"""

_TEXT_ONLINE_ORDERABLE_STORE_AVAILABLE = """\
online bestellbar
HORNBACH Hamburg
im Markt vorrätig
"""

_TEXT_ONLY_ONLINE_SIGNAL_NOT_ORDERABLE = """\
Z.ZT. NICHT ONLINE BESTELLBAR
HORNBACH Hamburg
"""

_TEXT_ONLY_STORE_SIGNAL_NOT_AVAILABLE = """\
HORNBACH Hamburg
Z.Zt. nicht im Markt vorrätig
"""

_TEXT_ONLY_STORE_SIGNAL_AVAILABLE = """\
HORNBACH Hamburg
im Markt vorrätig
"""


# ---------------------------------------------------------------------------
# Fixtures — HTML with price
# ---------------------------------------------------------------------------

_HTML_WITH_JSONLD_PRICE_LIST = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Klimasplitgerät Midea PortaSplit",
  "sku": "12356554",
  "offers": [
    {
      "@type": "Offer",
      "priceCurrency": "EUR",
      "price": "749.00"
    }
  ]
}
</script>
</body></html>
"""

_HTML_WITH_JSONLD_PRICE_DICT = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Klimasplitgerät Midea PortaSplit",
  "sku": "12356554",
  "offers": {
    "@type": "Offer",
    "priceCurrency": "EUR",
    "price": "749.00"
  }
}
</script>
</body></html>
"""

_HTML_JSONLD_PRICE_COMMA = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "offers": [{"@type": "Offer", "price": "749,00"}]
}
</script>
</body></html>
"""

_HTML_VISIBLE_PRICE_FALLBACK = """\
<html><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "offers": [{"@type": "Offer"}]
}
</script>
<span>749,00 €</span>
</body></html>
"""

_HTML_NO_PRICE = """\
<html><body>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","offers":[{"@type":"Offer"}]}
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
# Unit tests — parse_availability_signals() (pure, no browser)
# ---------------------------------------------------------------------------


def test_both_signals_absent_returns_none_none():
    """Anti-silent-failure: no signals found → (None, None)."""
    online, store = parse_availability_signals(_TEXT_NEITHER_ONLINE_NOR_STORE)
    assert online is None
    assert store is None


def test_online_not_orderable_store_not_available():
    online, store = parse_availability_signals(
        _TEXT_ONLINE_NOT_ORDERABLE_STORE_NOT_AVAILABLE
    )
    assert online is False
    assert store is False


def test_online_not_orderable_store_available():
    online, store = parse_availability_signals(
        _TEXT_ONLINE_NOT_ORDERABLE_STORE_AVAILABLE
    )
    assert online is False
    assert store is True


def test_online_orderable_store_not_available():
    online, store = parse_availability_signals(
        _TEXT_ONLINE_ORDERABLE_STORE_NOT_AVAILABLE
    )
    assert online is True
    assert store is False


def test_online_orderable_store_available():
    online, store = parse_availability_signals(_TEXT_ONLINE_ORDERABLE_STORE_AVAILABLE)
    assert online is True
    assert store is True


def test_only_online_signal_not_orderable():
    """Store signal absent → store=None."""
    online, store = parse_availability_signals(_TEXT_ONLY_ONLINE_SIGNAL_NOT_ORDERABLE)
    assert online is False
    assert store is None


def test_only_store_signal_not_available():
    """Online signal absent → online=None."""
    online, store = parse_availability_signals(_TEXT_ONLY_STORE_SIGNAL_NOT_AVAILABLE)
    assert online is None
    assert store is False


def test_only_store_signal_available():
    """Online signal absent → online=None; store positive form → store=True."""
    online, store = parse_availability_signals(_TEXT_ONLY_STORE_SIGNAL_AVAILABLE)
    assert online is None
    assert store is True


def test_case_insensitive_online():
    """Signals should match case-insensitively."""
    online, store = parse_availability_signals(
        "z.zt. nicht online bestellbar\nhornbach hamburg"
    )
    assert online is False


def test_case_insensitive_store():
    online, store = parse_availability_signals(
        "z.zt. nicht im markt vorrätig"
    )
    assert store is False


# ---------------------------------------------------------------------------
# Offer construction logic via combined signals (unit-tested inline)
# ---------------------------------------------------------------------------


def test_available_when_online_is_true():
    """available = True when online available, regardless of store."""
    online, store = True, False
    available = bool(online) or bool(store)
    pickup_only = bool(store) and not bool(online)
    assert available is True
    assert pickup_only is False


def test_available_when_store_is_true_not_online():
    """available = True when store available; pickup_only = True."""
    online, store = False, True
    available = bool(online) or bool(store)
    pickup_only = bool(store) and not bool(online)
    assert available is True
    assert pickup_only is True


def test_not_available_when_both_false():
    """available = False when both signals are negative."""
    online, store = False, False
    available = bool(online) or bool(store)
    pickup_only = bool(store) and not bool(online)
    assert available is False
    assert pickup_only is False


def test_not_available_when_online_none_store_false():
    """online=None treated as False → not available."""
    online, store = None, False
    available = bool(online) or bool(store)
    pickup_only = bool(store) and not bool(online)
    assert available is False


def test_available_when_online_none_store_true():
    """online=None store=True → pickup_only but available."""
    online, store = None, True
    available = bool(online) or bool(store)
    pickup_only = bool(store) and not bool(online)
    assert available is True
    assert pickup_only is True


# ---------------------------------------------------------------------------
# Unit tests — parse_price_from_html() (pure, no browser)
# ---------------------------------------------------------------------------


def test_price_from_jsonld_list():
    """Hornbach puts offers as a list — first element's price is used."""
    assert parse_price_from_html(_HTML_WITH_JSONLD_PRICE_LIST) == 749.0


def test_price_from_jsonld_dict():
    """Handle offers as a plain dict (future-proof)."""
    assert parse_price_from_html(_HTML_WITH_JSONLD_PRICE_DICT) == 749.0


def test_price_from_jsonld_comma():
    """Comma decimal separator handled."""
    assert parse_price_from_html(_HTML_JSONLD_PRICE_COMMA) == 749.0


def test_price_fallback_to_visible_text():
    """Falls back to visible '749,00 €' when JSON-LD offer has no price."""
    assert parse_price_from_html(_HTML_VISIBLE_PRICE_FALLBACK) == 749.0


def test_no_price_returns_none():
    assert parse_price_from_html(_HTML_NO_PRICE) is None


def test_no_product_jsonld_falls_back_to_visible():
    """Non-Product JSON-LD blocks skipped; visible price found."""
    assert parse_price_from_html(_HTML_NO_PRODUCT_JSONLD) == 749.0


def test_empty_html_returns_none():
    assert parse_price_from_html("<html></html>") is None


# ---------------------------------------------------------------------------
# Registry smoke tests (no browser)
# ---------------------------------------------------------------------------


def test_hornbach_in_known_sources():
    from src.sources import KNOWN_SOURCES, get_check, unknown_sources

    assert "hornbach" in KNOWN_SOURCES
    assert unknown_sources(["hornbach"]) == []
    fn = get_check("hornbach")
    assert callable(fn)


def test_get_check_hornbach_is_playwright_not_jsonld_spec():
    """get_check('hornbach') must return the Playwright check, not a lambda over SPECS."""
    from src.sources import SPECS, get_check

    assert "hornbach" not in SPECS, (
        "hornbach must NOT be in SPECS — it would route to the old httpx path"
    )
    fn = get_check("hornbach")
    from src.sources import hornbach

    assert fn is hornbach.check


# ---------------------------------------------------------------------------
# Browser integration test — skipped unless HORNBACH_BROWSER_TESTS=1
# ---------------------------------------------------------------------------

_BROWSER_REASON = (
    "Set HORNBACH_BROWSER_TESTS=1 to run live Playwright integration test "
    "(requires network + chromium headless-shell)"
)


@pytest.mark.skipif(
    os.environ.get("HORNBACH_BROWSER_TESTS") != "1",
    reason=_BROWSER_REASON,
)
def test_check_live():
    """Live browser test: runs check() for real and prints the resulting Offer."""
    from src.sources.hornbach import check

    offer = check(None)  # client is ignored

    print(f"\nLive Offer: {offer}")

    assert offer is not None, "check() returned None — anti-silent-failure triggered"
    assert offer.source == "hornbach"
    assert offer.ean == "4048164116478"
    assert offer.url.startswith("https://www.hornbach.de/")
    assert isinstance(offer.available, bool)
    assert isinstance(offer.pickup_only, bool)
    if offer.price is not None:
        assert 100 < offer.price < 2000, f"Implausible price: {offer.price}"
    print(f"\navailable={offer.available}, pickup_only={offer.pickup_only}, price={offer.price}")
