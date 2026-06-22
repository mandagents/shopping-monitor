from dataclasses import dataclass

import yaml


@dataclass(frozen=True)
class ProductConfig:
    ean: str
    model_no: str
    match_require_all: list
    match_require_any: list
    match_exclude_any: list


@dataclass(frozen=True)
class Config:
    product: ProductConfig
    max_price_eur: float
    sources_enabled: list
    hamburg_pickup_priority: bool
    health_fail_threshold: int


def load_config(path: str) -> Config:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    p = data["product"]
    product = ProductConfig(
        ean=str(p["ean"]),
        model_no=str(p.get("model_no", "")),
        match_require_all=list(p.get("match_require_all", [])),
        match_require_any=list(p.get("match_require_any", [])),
        match_exclude_any=list(p.get("match_exclude_any", [])),
    )
    return Config(
        product=product,
        max_price_eur=float(data["max_price_eur"]),
        sources_enabled=list(data["sources_enabled"]),
        hamburg_pickup_priority=bool(data.get("hamburg_pickup_priority", True)),
        health_fail_threshold=int(data.get("health_fail_threshold", 3)),
    )
