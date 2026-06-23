"""Tests for src/filter.py — multi-product matching + alert logic."""
from src.config import ProductConfig
from src.filter import match_product, matches_product, should_alert
from src.models import Offer

# ---------------------------------------------------------------------------
# Shared product fixtures
# ---------------------------------------------------------------------------

PRODUCT_35 = ProductConfig(
    name="Midea PortaSplit 3,5 kW (Wärmepumpe)",
    ean="4048164116478",
    model_no="10002085",
    max_price_eur=850.0,
    match_require_all=["portasplit"],
    match_require_any=["12000", "12.000", "3,5", "3.5"],
    match_exclude_any=["cool", "2,35", "2.35"],
)

PRODUCT_COOL = ProductConfig(
    name="Midea PortaSplit Cool 2,35 kW",
    ean="",
    model_no="",
    max_price_eur=850.0,
    match_require_all=["portasplit", "cool"],
    match_require_any=["2,35", "2.35", "2350"],
    match_exclude_any=[],
)

PRODUCTS = [PRODUCT_35, PRODUCT_COOL]


def _offer(**kw):
    base = dict(source="x", title="", url="u", price=799.0, available=True,
                pickup_only=False, ean=None)
    base.update(kw)
    return Offer(**base)


# ---------------------------------------------------------------------------
# matches_product() — back-compat single-product helper
# ---------------------------------------------------------------------------

def test_ean_match_wins_when_present():
    assert matches_product(_offer(ean="4048164116478"), PRODUCT_35) is True
    assert matches_product(_offer(ean="9999999999999"), PRODUCT_35) is False


def test_name_match_for_toom_without_ean():
    assert matches_product(_offer(title="Midea PortaSplit 12000 BTU/h"), PRODUCT_35) is True


def test_name_match_excludes_comfee_cool():
    assert matches_product(_offer(title="Comfee PortaSplit Cool 2,35kW"), PRODUCT_35) is False


# ---------------------------------------------------------------------------
# match_product() — multi-product routing
# ---------------------------------------------------------------------------

def test_35kw_offer_by_ean_matches_only_35kw():
    """3,5 kW offer carrying the known EAN must map to PRODUCT_35 only."""
    offer = _offer(ean="4048164116478", title="Midea PortaSplit 12000 BTU")
    result = match_product(offer, PRODUCTS)
    assert result is PRODUCT_35


def test_35kw_offer_by_ean_does_not_match_cool():
    """The Cool product has no EAN; the 3,5 kW EAN must not fall through to Cool."""
    offer = _offer(ean="4048164116478", title="Midea PortaSplit 12000 BTU")
    # Verify directly that it does NOT match PRODUCT_COOL individually.
    # PRODUCT_COOL has ean="" (falsy), offer has ean set → name-match path.
    # Title lacks "cool" → _name_match fails → no match.
    assert matches_product(offer, PRODUCT_COOL) is False


def test_cool_offer_no_ean_matches_cool_product():
    """Cool offer (ean=None, title contains portasplit+cool+2,35) → PRODUCT_COOL."""
    offer = _offer(ean=None, title="Midea PortaSplit Cool 2,35 kW — AliExpress (Versand DE)")
    result = match_product(offer, PRODUCTS)
    assert result is PRODUCT_COOL


def test_cool_offer_does_not_match_35kw():
    """Cool offer must NOT match 3,5 kW product (exclude_any=["cool","2,35"])."""
    offer = _offer(ean=None, title="Midea PortaSplit Cool 2,35 kW — AliExpress (Versand DE)")
    assert matches_product(offer, PRODUCT_35) is False


def test_35kw_name_only_offer_does_not_match_cool():
    """A plain 3,5 kW name-only offer must not accidentally match the Cool product."""
    offer = _offer(ean=None, title="Midea PortaSplit 12000 BTU 3,5 kW")
    # Must match 3,5 kW (has require_all=portasplit, require_any=3,5)
    assert matches_product(offer, PRODUCT_35) is True
    # Must NOT match Cool (require_all includes "cool" which is absent)
    assert matches_product(offer, PRODUCT_COOL) is False


def test_unrelated_offer_matches_nothing():
    offer = _offer(ean=None, title="Dyson V15 Detect vacuum cleaner")
    assert match_product(offer, PRODUCTS) is None


def test_match_product_returns_none_for_empty_list():
    offer = _offer(ean="4048164116478")
    assert match_product(offer, []) is None


# ---------------------------------------------------------------------------
# should_alert() — new signature: (offer, products)
# ---------------------------------------------------------------------------

def test_should_alert_35kw_in_stock_good_price():
    offer = _offer(ean="4048164116478", price=749.0, available=True)
    assert should_alert(offer, PRODUCTS) is True


def test_should_alert_35kw_over_cap():
    offer = _offer(ean="4048164116478", price=999.0, available=True)
    assert should_alert(offer, PRODUCTS) is False


def test_should_alert_35kw_unavailable():
    offer = _offer(ean="4048164116478", price=749.0, available=False)
    assert should_alert(offer, PRODUCTS) is False


def test_should_alert_35kw_at_exact_cap():
    offer = _offer(ean="4048164116478", price=850.0, available=True)
    assert should_alert(offer, PRODUCTS) is True


def test_should_alert_false_when_price_unknown():
    offer = _offer(ean="4048164116478", price=None, available=True)
    assert should_alert(offer, PRODUCTS) is False


def test_should_alert_cool_in_stock_good_price():
    offer = _offer(ean=None, title="Midea PortaSplit Cool 2,35 kW AliExpress",
                   price=699.0, available=True)
    assert should_alert(offer, PRODUCTS) is True


def test_should_alert_cool_over_cap():
    offer = _offer(ean=None, title="Midea PortaSplit Cool 2,35 kW AliExpress",
                   price=900.0, available=True)
    assert should_alert(offer, PRODUCTS) is False


def test_should_alert_cool_unavailable():
    offer = _offer(ean=None, title="Midea PortaSplit Cool 2,35 kW AliExpress",
                   price=699.0, available=False)
    assert should_alert(offer, PRODUCTS) is False


def test_should_alert_per_product_price_cap():
    """Price cap is applied per matched product, not globally."""
    # 3,5 kW cap is 850; Cool cap also 850 in the fixture — change 3,5 kW cap to 700
    product_35_low_cap = ProductConfig(
        name="Midea PortaSplit 3,5 kW (Wärmepumpe)",
        ean="4048164116478",
        model_no="10002085",
        max_price_eur=700.0,
        match_require_all=["portasplit"],
        match_require_any=["12000", "3,5"],
        match_exclude_any=["cool", "2,35"],
    )
    products = [product_35_low_cap, PRODUCT_COOL]
    # 749 > 700 → no alert for 3,5 kW
    offer_35 = _offer(ean="4048164116478", price=749.0, available=True)
    assert should_alert(offer_35, products) is False
    # Cool offer at 749 ≤ 850 → alert
    offer_cool = _offer(ean=None, title="Midea PortaSplit Cool 2,35 kW", price=749.0, available=True)
    assert should_alert(offer_cool, products) is True
