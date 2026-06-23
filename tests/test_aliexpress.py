"""Tests for the AliExpress source.

Unit tests cover the pure parsing helpers — no browser needed.
The live browser integration test is guarded by ``ALIEXPRESS_BROWSER_TESTS=1``
so ``.venv/bin/python -m pytest -q`` stays green without a browser or network.
"""
from __future__ import annotations

import os

import pytest

from src.sources.aliexpress import (
    extract_price_from_run_params,
    is_bot_challenge,
    is_unavailable,
    parse_embedded_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Page text that contains the "item unavailable in your region" marker
_PAGE_TEXT_UNAVAILABLE = (
    "leider ist dieser artikel an ihrem standort derzeit nicht verfügbar"
    " und einige andere text"
)

# Page text for a normally-rendered product page (no unavailability marker)
_PAGE_TEXT_AVAILABLE = (
    "midea portasplit 12000 btu klimaanlage kaufen preis 569,00 € in den warenkorb"
)

# A representative runParams dict with price info
_RUN_PARAMS_WITH_PRICE: dict = {
    "data": {
        "priceModule": {
            "minAmount": {"value": 569.0, "currency": "EUR"},
            "maxAmount": {"value": 569.0, "currency": "EUR"},
            "formatedPrice": "€ 569,00",
        }
    }
}

# A runParams dict where the price is only in the formatted string
_RUN_PARAMS_FORMATTED_ONLY: dict = {
    "data": {
        "priceModule": {
            "formatedActivityPrice": "€ 549,99",
        }
    }
}

# A malformed / missing priceModule
_RUN_PARAMS_NO_PRICE: dict = {
    "data": {
        "titleModule": {"subject": "some product"},
    }
}

# Minimal rendered HTML embedding runParams with a price
_HTML_WITH_RUN_PARAMS = """
<html><head></head><body>
<script>
window.runParams = {"data":{"priceModule":{"minAmount":{"value":569.0,"currency":"EUR"},
"formatedPrice":"\\u20ac 569,00"}}};
</script>
<div>some content</div>
</body></html>
"""

# Rendered HTML with priceModule embedded directly (no window.runParams wrapper)
_HTML_WITH_PRICE_MODULE_DIRECT = """
<html><head></head><body>
<script type="text/javascript">
var data = {"priceModule":{"minActivityAmount":{"value":499.00},"formatedPrice":"499,00 \\u20ac"}};
</script>
</body></html>
"""

# Rendered HTML that contains no extractable price data
_HTML_NO_PRICE = """
<html><head></head><body>
<script>
var x = {"titleModule": {"subject": "Midea PortaSplit"}};
</script>
<div>82,39 €</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# is_unavailable() — tests for the availability marker detection
# ---------------------------------------------------------------------------


def test_unavailable_marker_detected():
    """Page with the canonical AliExpress 'not available' text → unavailable."""
    assert is_unavailable(_PAGE_TEXT_UNAVAILABLE) is True


def test_available_page_not_flagged_as_unavailable():
    """A normal product page should not trigger the unavailability marker."""
    assert is_unavailable(_PAGE_TEXT_AVAILABLE) is False


def test_empty_text_is_not_unavailable():
    assert is_unavailable("") is False


def test_english_unavailable_marker_detected():
    assert is_unavailable("this item is currently not available for purchase") is True


# ---------------------------------------------------------------------------
# is_bot_challenge() — bot / punish page detection
# ---------------------------------------------------------------------------


def test_punish_in_url_is_challenge():
    assert is_bot_challenge("https://www.aliexpress.com/punish/verify", "normal page") is True


def test_tmd_in_url_is_challenge():
    assert is_bot_challenge("https://www.aliexpress.com/_____tmd_____/punish", "") is True


def test_challenge_text_in_page_is_challenge():
    assert is_bot_challenge("https://de.aliexpress.com/item/123.html",
                            "please slide to verify your identity") is True


def test_normal_url_and_text_not_challenge():
    assert is_bot_challenge("https://de.aliexpress.com/item/1005012500647890.html",
                            "midea portasplit 569 eur kaufen") is False


# ---------------------------------------------------------------------------
# extract_price_from_run_params() — price extraction from data dict
# ---------------------------------------------------------------------------


def test_extracts_price_from_min_amount_value():
    """Standard minAmount.value path returns a float price."""
    price = extract_price_from_run_params(_RUN_PARAMS_WITH_PRICE)
    assert price == 569.0


def test_extracts_price_from_formatted_string():
    """Falls back to formatedActivityPrice when numeric fields absent."""
    price = extract_price_from_run_params(_RUN_PARAMS_FORMATTED_ONLY)
    assert price == 549.99


def test_returns_none_when_no_price_module():
    """Missing priceModule → None (anti-silent-failure)."""
    price = extract_price_from_run_params(_RUN_PARAMS_NO_PRICE)
    assert price is None


def test_returns_none_for_empty_dict():
    assert extract_price_from_run_params({}) is None


def test_handles_price_module_passed_directly():
    """If caller passes a dict with priceModule at the top level."""
    obj = {
        "priceModule": {
            "minAmount": {"value": 399.0},
        }
    }
    price = extract_price_from_run_params(obj)
    assert price == 399.0


# ---------------------------------------------------------------------------
# parse_embedded_data() — end-to-end HTML → price
# ---------------------------------------------------------------------------


def test_parse_embedded_run_params():
    """Detects window.runParams blob and extracts the price."""
    price = parse_embedded_data(_HTML_WITH_RUN_PARAMS)
    assert price == 569.0


def test_parse_price_module_direct():
    """Detects a priceModule JSON object embedded directly in a <script>."""
    price = parse_embedded_data(_HTML_WITH_PRICE_MODULE_DIRECT)
    assert price == 499.0


def test_parse_no_price_returns_none():
    """HTML with no product price data → None (anti-silent-failure).

    The page contains "82,39 €" which belongs to a recommendation widget —
    parse_embedded_data must NOT pick that up as the product price.
    """
    price = parse_embedded_data(_HTML_NO_PRICE)
    assert price is None


def test_parse_empty_html_returns_none():
    assert parse_embedded_data("<html></html>") is None


# ---------------------------------------------------------------------------
# Registry smoke test
# ---------------------------------------------------------------------------


def test_aliexpress_in_known_sources():
    from src.sources import KNOWN_SOURCES, get_check, unknown_sources

    assert "aliexpress" in KNOWN_SOURCES
    assert unknown_sources(["aliexpress"]) == []
    assert callable(get_check("aliexpress"))


# ---------------------------------------------------------------------------
# Live browser integration test — skipped unless ALIEXPRESS_BROWSER_TESTS=1
# ---------------------------------------------------------------------------

_BROWSER_REASON = (
    "Set ALIEXPRESS_BROWSER_TESTS=1 to run the live Playwright integration "
    "test (requires network + chromium headless-shell; AliExpress may block "
    "datacenter IPs with a bot-challenge — that returns None, not a failure)."
)


@pytest.mark.skipif(
    os.environ.get("ALIEXPRESS_BROWSER_TESTS") != "1",
    reason=_BROWSER_REASON,
)
def test_check_live():
    """Live browser test: run check() for real and assert the Offer shape.

    The item (Midea PortaSplit, item 1005012500647890) is currently UNAVAILABLE
    on AliExpress DE — the expected outcome is Offer(available=False).
    If AliExpress blocks headless with a bot-challenge, check() returns None —
    this test will fail in that case (and you should note the CI IP-block risk).
    """
    from src.sources.aliexpress import URL, EAN, NAME, check

    offer = check(None)

    print(f"\nLive Offer: {offer}")

    # If we got None the page was bot-challenged — flag it clearly.
    assert offer is not None, (
        "check() returned None — AliExpress challenged the headless browser "
        "(bot-protection / slider / punish page).  CI IP-block risk is real."
    )

    assert offer.source == NAME
    assert offer.ean == EAN
    assert offer.url == URL
    assert offer.pickup_only is False
    assert isinstance(offer.available, bool)

    # Currently unavailable — assert so the test documents reality.
    # Remove/change this assertion when the item becomes available again.
    assert offer.available is False, (
        f"Item appears available (price={offer.price}) — "
        "verify this is real (not a false-positive from a recommendation widget)"
    )

    if offer.price is not None:
        # Price should only be present when available=True (see logic above)
        assert offer.available is True
        assert 50 < offer.price < 2000, f"Implausible price: {offer.price}"
