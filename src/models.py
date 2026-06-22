from dataclasses import dataclass


@dataclass(frozen=True)
class Offer:
    source: str
    title: str
    url: str
    price: float | None
    available: bool
    pickup_only: bool = False
    ean: str | None = None
