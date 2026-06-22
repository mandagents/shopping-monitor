import json

from bs4 import BeautifulSoup

_AVAILABLE = {"instock", "limitedavailability", "onlineonly", "instoreonline"}


def extract_jsonld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            blocks.extend([d for d in data if isinstance(d, dict)])
        elif isinstance(data, dict):
            blocks.append(data)
    return blocks


def _flatten(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for b in blocks:
        graph = b.get("@graph")
        if isinstance(graph, list):
            out.extend([g for g in graph if isinstance(g, dict)])
        else:
            out.append(b)
    return out


def find_product(blocks: list[dict]) -> dict | None:
    for b in _flatten(blocks):
        t = b.get("@type")
        if t == "Product" or (isinstance(t, list) and "Product" in t):
            return b
    return None


def first_offer(product: dict) -> dict | None:
    offers = product.get("offers")
    if isinstance(offers, list):
        return offers[0] if offers else None
    if isinstance(offers, dict):
        return offers
    return None


def availability_state(av: str | None) -> tuple[bool, bool]:
    if not isinstance(av, str) or not av:
        return (False, False)
    token = av.rstrip("/").rsplit("/", 1)[-1].lower()
    # NOTE: schema.org `InStoreOnly` is deliberately NOT treated as available.
    # Some retailers (e.g. OBI, Hagebau) emit it as a static catalog flag even
    # when the item is sold out ("derzeit nicht verfügbar" / "Ausverkauft"),
    # which produced false-positive alerts. Only genuine buyable states count.
    # Reliable per-store pickup detection is a v2 task.
    if token in _AVAILABLE:
        return (True, False)
    return (False, False)


def offer_price(offer: dict, mode: str) -> float | None:
    if mode == "aggregate":
        val = offer.get("lowPrice")
        if val is None:
            val = offer.get("price")
    else:
        val = offer.get("price")
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "."))
    except ValueError:
        return None
