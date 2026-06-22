import re

from ..jsonld import availability_state, extract_jsonld, find_product, first_offer
from ..models import Offer
from .base import fetch

NAME = "toom"
URL = "https://toom.de/p/mobiles-klimageraet-portasplit-12000-btuh/9350668"
_PRICE_RE = re.compile(r"(\d{2,4})[.,](\d{2})\s*€")


def parse(html: str) -> Offer | None:
    product = find_product(extract_jsonld(html))
    if product is None:
        return None
    offer = first_offer(product)
    if offer is None or offer.get("availability") is None:
        return None
    available, pickup_only = availability_state(offer.get("availability"))
    m = _PRICE_RE.search(html)
    if m is None:
        return None  # toom zeigt sonst immer einen Preis -> kein Match = Layout kaputt = Fehlschlag
    price = float(f"{m.group(1)}.{m.group(2)}")
    return Offer(
        source=NAME,
        title=str(product.get("name", "")),
        url=URL,
        price=price,
        available=available,
        pickup_only=pickup_only,
        ean=None,
    )


def check(client) -> Offer | None:
    return parse(fetch(client, URL))
