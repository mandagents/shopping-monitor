from dataclasses import dataclass

from ..jsonld import (
    availability_state,
    extract_jsonld,
    find_product,
    first_offer,
    offer_price,
)
from ..models import Offer

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class SourceSpec:
    name: str
    url: str
    price_mode: str = "offer"
    trust_ean: bool = True


def fetch(client, url: str) -> str:
    resp = client.get(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        },
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.text


def parse_jsonld_source(html: str, spec: SourceSpec) -> Offer | None:
    product = find_product(extract_jsonld(html))
    if product is None:
        return None
    offer = first_offer(product)
    availability = offer.get("availability") if offer else None
    if offer is None or availability is None:
        return None  # Silent-OOS-Schutz: unbekannte Verfügbarkeit = Fehlschlag
    available, pickup_only = availability_state(availability)
    ean = None
    if spec.trust_ean:
        ean = product.get("gtin13") or product.get("gtin") or None
    return Offer(
        source=spec.name,
        title=str(product.get("name", "")),
        url=spec.url,
        price=offer_price(offer, spec.price_mode),
        available=available,
        pickup_only=pickup_only,
        ean=str(ean) if ean else None,
    )


def check_jsonld(client, spec: SourceSpec) -> Offer | None:
    return parse_jsonld_source(fetch(client, spec.url), spec)
