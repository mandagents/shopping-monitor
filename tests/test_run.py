from src.models import Offer
from src.run import format_offer


def _offer(**kw):
    base = dict(source="obi", title="Midea PortaSplit", url="https://obi.example/p",
                price=799.0, available=True, pickup_only=False, ean="4048164116478")
    base.update(kw)
    return Offer(**base)


def test_format_offer_normal_price_and_url():
    text, url = format_offer(_offer(price=799.0))
    assert "799.00 €" in text
    assert "obi" in text
    assert url == "https://obi.example/p"


def test_format_offer_pickup_marker_present_when_pickup_only():
    text, _ = format_offer(_offer(pickup_only=True))
    assert "Abholung" in text


def test_format_offer_no_pickup_marker_when_not_pickup_only():
    text, _ = format_offer(_offer(pickup_only=False))
    assert "Abholung" not in text


def test_format_offer_handles_unknown_price():
    text, _ = format_offer(_offer(price=None))
    assert "Preis unbekannt" in text
