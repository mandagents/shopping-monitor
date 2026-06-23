from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class ProductConfig:
    name: str
    ean: str
    model_no: str
    max_price_eur: float
    match_require_all: list
    match_require_any: list
    match_exclude_any: list


@dataclass(frozen=True)
class Config:
    products: list
    sources_enabled: list
    hamburg_pickup_priority: bool
    health_fail_threshold: int
    woklima_enabled: bool = False
    woklima_country: str = "de"


def load_config(path: str) -> Config:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    products = []
    for p in data["products"]:
        products.append(ProductConfig(
            name=str(p.get("name", "")),
            ean=str(p.get("ean", "")),
            model_no=str(p.get("model_no", "")),
            max_price_eur=float(p["max_price_eur"]),
            match_require_all=list(p.get("match_require_all", [])),
            match_require_any=list(p.get("match_require_any", [])),
            match_exclude_any=list(p.get("match_exclude_any", [])),
        ))
    return Config(
        products=products,
        sources_enabled=list(data["sources_enabled"]),
        hamburg_pickup_priority=bool(data.get("hamburg_pickup_priority", True)),
        health_fail_threshold=int(data.get("health_fail_threshold", 3)),
        woklima_enabled=bool(data.get("woklima_enabled", False)),
        woklima_country=str(data.get("woklima_country", "de")),
    )
