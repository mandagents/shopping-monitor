from src.config import Config, ProductConfig
from src.filter import matches_product, should_alert
from src.models import Offer

PRODUCT = ProductConfig(
    ean="4048164116478",
    model_no="10002085",
    match_require_all=["portasplit"],
    match_require_any=["12000", "3,5"],
    match_exclude_any=["cool", "2,35"],
)
CFG = Config(
    product=PRODUCT,
    max_price_eur=850.0,
    sources_enabled=["obi", "toom"],
    hamburg_pickup_priority=True,
    health_fail_threshold=3,
)


def _offer(**kw):
    base = dict(source="x", title="", url="u", price=799.0, available=True,
                pickup_only=False, ean=None)
    base.update(kw)
    return Offer(**base)


def test_ean_match_wins_when_present():
    assert matches_product(_offer(ean="4048164116478"), PRODUCT) is True
    assert matches_product(_offer(ean="9999999999999"), PRODUCT) is False


def test_name_match_for_toom_without_ean():
    assert matches_product(_offer(title="Midea PortaSplit 12000 BTU/h"), PRODUCT) is True


def test_name_match_excludes_comfee_cool():
    assert matches_product(_offer(title="Comfee PortaSplit Cool 2,35kW"), PRODUCT) is False


def test_should_alert_only_in_stock_at_or_below_max_price():
    assert should_alert(_offer(ean="4048164116478", price=749.0, available=True), CFG) is True
    assert should_alert(_offer(ean="4048164116478", price=999.0, available=True), CFG) is False
    assert should_alert(_offer(ean="4048164116478", price=749.0, available=False), CFG) is False
    assert should_alert(_offer(ean="4048164116478", price=850.0, available=True), CFG) is True


def test_should_alert_false_when_price_unknown():
    assert should_alert(_offer(ean="4048164116478", price=None, available=True), CFG) is False
