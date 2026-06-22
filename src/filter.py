from .config import Config, ProductConfig
from .models import Offer


def matches_product(offer: Offer, p: ProductConfig) -> bool:
    if offer.ean:
        return offer.ean == p.ean
    title = (offer.title or "").lower()
    if any(x.lower() in title for x in p.match_exclude_any):
        return False
    if not all(x.lower() in title for x in p.match_require_all):
        return False
    return any(x.lower() in title for x in p.match_require_any)


def should_alert(offer: Offer, cfg: Config) -> bool:
    if not matches_product(offer, cfg.product):
        return False
    if not offer.available:
        return False
    if offer.price is None or offer.price > cfg.max_price_eur:
        return False
    return True
