# Midea PortaSplit Verfügbarkeits-Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Python-Bot, der 6 Shops/Aggregatoren auf Verfügbarkeit der Midea PortaSplit (EAN 4048164116478) prüft und bei „verfügbar ≤ 850 €" sofort per Telegram benachrichtigt; läuft alle 5 Min auf GitHub Actions.

**Architecture:** Pro Lauf fragt eine Orchestrierung (`run_once`) alle aktivierten Quellen ab. Fünf Quellen teilen sich einen generischen schema.org-JSON-LD-Parser (Produkt → Preis + Verfügbarkeit + EAN); toom hat einen Sonderparser (sichtbarer Preis statt unbrauchbarem JSON-LD-Preis, Name- statt EAN-Match). Ein Filter entscheidet (Identität + verfügbar + Preis ≤ MAX_PRICE), ein State-Layer entstört (Dedupe), ein Health-Layer meldet kaputte Quellen. Benachrichtigung via Telegram-Bot-API. State persistiert über GitHub Actions Cache.

**Tech Stack:** Python 3.12, httpx (HTTP), BeautifulSoup4 (JSON-LD-Extraktion), PyYAML (Config), pytest (Tests), GitHub Actions (Cron + Secrets).

## Global Constraints

- **Produkt-Anker EAN/GTIN-13:** `4048164116478` — wo eine Quelle `gtin13` liefert, MUSS dieser Wert matchen (sonst falsches Produkt, z.B. „Comfee Cool").
- **MAX_PRICE:** `850` EUR — nur melden bei Preis ≤ diesem Wert.
- **Abholung zählt:** schema.org `InStoreOnly` / Filialbestand gilt als „verfügbar".
- **v1-Quellen:** `idealo`, `hornbach`, `obi`, `toom`, `bauhaus`, `hagebau`.
- **Keine Secrets im Code:** `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` ausschließlich aus Umgebungsvariablen / GitHub Secrets.
- **Kein Server-Checkout:** Bot meldet nur, Kauf erfolgt manuell. Keine Login-/Zahlungsdaten.
- **Cron:** `*/5 * * * *` (alle 5 Min) + manueller `workflow_dispatch`.
- **Silent-OOS-Schutz:** Findet eine JSON-LD-Quelle kein Produkt ODER kein Verfügbarkeits-Feld → gilt als Fehlschlag (Health-Check), NICHT als „nicht verfügbar".
- **TDD, DRY, YAGNI, häufige Commits.** Tests laufen mit `python -m pytest`.

---

## File Structure

```
shopping-monitor/
├── requirements.txt              # httpx, beautifulsoup4, PyYAML, pytest
├── config.yaml                   # Produkt, MAX_PRICE, Quellen, Health-Schwelle
├── src/
│   ├── __init__.py
│   ├── models.py                 # Offer-Dataclass
│   ├── config.py                 # Config/ProductConfig + load_config()
│   ├── jsonld.py                 # JSON-LD-Extraktion + Verfügbarkeits-Mapping
│   ├── filter.py                 # matches_product() + should_alert()
│   ├── state.py                  # load/save State + Dedupe (is_new_alert)
│   ├── health.py                 # record_failure/record_success
│   ├── notify.py                 # send_telegram()
│   ├── monitor.py                # run_once() Orchestrierung
│   ├── run.py                    # main() Entry-Point (wirt reale Deps)
│   └── sources/
│       ├── __init__.py           # SPECS-Registry + get_check()
│       ├── base.py               # SourceSpec, fetch(), parse_jsonld_source(), check_jsonld()
│       └── toom.py               # Sonderparser
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_jsonld.py
│   ├── test_base_source.py
│   ├── test_sources_registry.py
│   ├── test_toom.py
│   ├── test_filter.py
│   ├── test_state.py
│   ├── test_notify.py
│   ├── test_health.py
│   └── test_monitor.py
└── .github/workflows/monitor.yml # Cron-Workflow
```

---

### Task 1: Scaffolding, Dependencies, Models & Config

**Files:**
- Create: `requirements.txt`, `config.yaml`, `src/__init__.py`, `src/sources/__init__.py` (leer vorerst), `tests/__init__.py`, `src/models.py`, `src/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `src.models.Offer(source: str, title: str, url: str, price: float|None, available: bool, pickup_only: bool=False, ean: str|None=None)` (frozen dataclass)
  - `src.config.ProductConfig(ean, model_no, match_require_all, match_require_any, match_exclude_any)`
  - `src.config.Config(product, max_price_eur, sources_enabled, hamburg_pickup_priority, health_fail_threshold)`
  - `src.config.load_config(path: str) -> Config`

- [ ] **Step 1: Create dependency + scaffolding files**

`requirements.txt`:
```
httpx>=0.27
beautifulsoup4>=4.12
PyYAML>=6.0
pytest>=8.0
```

`src/__init__.py`, `src/sources/__init__.py`, `tests/__init__.py` — alle leer (leere Datei anlegen).

`config.yaml`:
```yaml
product:
  ean: "4048164116478"
  model_no: "10002085"
  match_require_all: ["portasplit"]
  match_require_any: ["12000", "12.000", "3,5", "3.5"]
  match_exclude_any: ["cool", "2,35", "2.35"]
max_price_eur: 850
sources_enabled: ["idealo", "hornbach", "obi", "toom", "bauhaus", "hagebau"]
hamburg_pickup_priority: true
health_fail_threshold: 3
```

- [ ] **Step 2: Write the failing test**

`tests/test_config.py`:
```python
from src.config import load_config


def test_load_config_reads_product_and_price(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "product:\n"
        '  ean: "4048164116478"\n'
        '  model_no: "10002085"\n'
        "  match_require_all: [portasplit]\n"
        "  match_require_any: ['12000']\n"
        "  match_exclude_any: [cool]\n"
        "max_price_eur: 850\n"
        "sources_enabled: [idealo, toom]\n"
        "hamburg_pickup_priority: true\n"
        "health_fail_threshold: 3\n"
    )
    cfg = load_config(str(cfg_file))
    assert cfg.product.ean == "4048164116478"
    assert cfg.max_price_eur == 850.0
    assert cfg.sources_enabled == ["idealo", "toom"]
    assert cfg.product.match_exclude_any == ["cool"]
    assert cfg.health_fail_threshold == 3
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 4: Write the implementation**

`src/models.py`:
```python
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
```

`src/config.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add requirements.txt config.yaml src/ tests/
git commit -m "feat: project scaffolding, Offer model and config loader"
```

---

### Task 2: JSON-LD Extraction & Availability Mapping

**Files:**
- Create: `src/jsonld.py`
- Test: `tests/test_jsonld.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `extract_jsonld(html: str) -> list[dict]`
  - `find_product(blocks: list[dict]) -> dict | None` (behandelt `@graph` und `@type`-Listen)
  - `first_offer(product: dict) -> dict | None` (behandelt `Offer`, `AggregateOffer`, Listen)
  - `availability_state(av: str | None) -> tuple[bool, bool]` → `(available, pickup_only)`
  - `offer_price(offer: dict, mode: str) -> float | None` (`mode` ∈ `"offer"`, `"aggregate"`)

- [ ] **Step 1: Write the failing test**

`tests/test_jsonld.py`:
```python
from src.jsonld import (
    availability_state,
    extract_jsonld,
    find_product,
    first_offer,
    offer_price,
)

OBI_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Midea PortaSplit",
 "gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStoreOnly","price":799.99,"priceCurrency":"EUR"}}
</script></head><body></body></html>
"""

IDEALO_HTML = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit 3,5 kW","gtin13":"4048164116478",
 "offers":{"@type":"AggregateOffer","lowPrice":999,"highPrice":1049,"offerCount":2,
 "availability":"https://schema.org/InStock"}}
</script>
"""


def test_find_product_and_offer_fields():
    product = find_product(extract_jsonld(OBI_HTML))
    assert product["gtin13"] == "4048164116478"
    offer = first_offer(product)
    assert offer_price(offer, "offer") == 799.99


def test_aggregate_offer_uses_low_price():
    product = find_product(extract_jsonld(IDEALO_HTML))
    assert offer_price(first_offer(product), "aggregate") == 999.0


def test_availability_state_mapping():
    assert availability_state("https://schema.org/InStock") == (True, False)
    assert availability_state("http://schema.org/InStoreOnly") == (True, True)
    assert availability_state("https://schema.org/OutOfStock") == (False, False)
    assert availability_state(None) == (False, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_jsonld.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.jsonld'`

- [ ] **Step 3: Write the implementation**

`src/jsonld.py`:
```python
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
    if token == "instoreonly":
        return (True, True)
    if token in _AVAILABLE:
        return (True, False)
    return (False, False)


def offer_price(offer: dict, mode: str) -> float | None:
    val = offer.get("lowPrice") if mode == "aggregate" else offer.get("price")
    if val is None:
        val = offer.get("price")
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "."))
    except ValueError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_jsonld.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/jsonld.py tests/test_jsonld.py
git commit -m "feat: JSON-LD extraction and schema.org availability mapping"
```

---

### Task 3: Generic JSON-LD Source (base.py)

**Files:**
- Create: `src/sources/base.py`
- Test: `tests/test_base_source.py`

**Interfaces:**
- Consumes: `src.jsonld.*`, `src.models.Offer`
- Produces:
  - `SourceSpec(name: str, url: str, price_mode: str="offer", trust_ean: bool=True)` (frozen dataclass)
  - `fetch(client, url: str) -> str` (GET mit realistischem UA, raise_for_status)
  - `parse_jsonld_source(html: str, spec: SourceSpec) -> Offer | None` (None = Fehlschlag: kein Produkt ODER kein `availability`-Feld)
  - `check_jsonld(client, spec: SourceSpec) -> Offer | None`

- [ ] **Step 1: Write the failing test**

`tests/test_base_source.py`:
```python
from src.sources.base import SourceSpec, parse_jsonld_source

OBI_INSTOREONLY = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"http://schema.org/InStoreOnly","price":799.99}}
</script>
"""

BAUHAUS_OOS = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea Klimasplitgerät PortaSplit 12.000 Btu","gtin13":"4048164116478",
 "offers":{"@type":"Offer","availability":"https://schema.org/OutOfStock","price":"749.00"}}
</script>
"""

NO_AVAILABILITY = """
<script type="application/ld+json">
{"@type":"Product","name":"Midea PortaSplit","gtin13":"4048164116478",
 "offers":{"@type":"Offer","price":749.0}}
</script>
"""


def test_parse_instoreonly_offer():
    spec = SourceSpec("obi", "https://obi.example/p/8620890")
    offer = parse_jsonld_source(OBI_INSTOREONLY, spec)
    assert offer.available is True
    assert offer.pickup_only is True
    assert offer.price == 799.99
    assert offer.ean == "4048164116478"
    assert offer.url == "https://obi.example/p/8620890"


def test_parse_out_of_stock_offer():
    spec = SourceSpec("bauhaus", "https://bauhaus.example/p/31934233")
    offer = parse_jsonld_source(BAUHAUS_OOS, spec)
    assert offer.available is False
    assert offer.price == 749.0


def test_missing_availability_is_failure():
    spec = SourceSpec("hornbach", "https://hornbach.example/p/12356554")
    assert parse_jsonld_source(NO_AVAILABILITY, spec) is None


def test_no_product_is_failure():
    spec = SourceSpec("x", "https://x.example")
    assert parse_jsonld_source("<html></html>", spec) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_base_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.sources.base'`

- [ ] **Step 3: Write the implementation**

`src/sources/base.py`:
```python
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
        headers={"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"},
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
    if offer is None or offer.get("availability") is None:
        return None  # Silent-OOS-Schutz: unbekannte Verfügbarkeit = Fehlschlag
    available, pickup_only = availability_state(offer.get("availability"))
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_base_source.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/sources/base.py tests/test_base_source.py
git commit -m "feat: generic JSON-LD source parser with silent-OOS protection"
```

---

### Task 4: Source Registry + 5 JSON-LD Sources

**Files:**
- Modify: `src/sources/__init__.py`
- Test: `tests/test_sources_registry.py`

**Interfaces:**
- Consumes: `src.sources.base.SourceSpec`, `src.sources.base.check_jsonld`, `src.sources.toom` (in Task 5 ergänzt — der Import wird hier bereits robust gegen Abwesenheit gebaut)
- Produces:
  - `SPECS: dict[str, SourceSpec]` für idealo/hornbach/obi/bauhaus/hagebau
  - `get_check(name: str) -> Callable[[client], Offer | None]`

**Hinweis zu hornbach:** Recon zeigte sauberes JSON-LD (Preis 749, gtin13). Falls Hornbach das `availability`-Feld weglässt, greift der Silent-OOS-Schutz aus Task 3 → Quelle meldet Fehlschlag → Health-Check (Task 9) warnt. So entsteht KEINE stille Blindheit. (Verifikation der echten Verfügbarkeits-Felder erfolgt im Go-Live, Task 11.)

- [ ] **Step 1: Write the failing test**

`tests/test_sources_registry.py`:
```python
from src.sources import SPECS, get_check


def test_all_v1_jsonld_sources_present():
    for name in ["idealo", "hornbach", "obi", "bauhaus", "hagebau"]:
        assert name in SPECS
        assert SPECS[name].url.startswith("https://")


def test_idealo_uses_aggregate_price_mode():
    assert SPECS["idealo"].price_mode == "aggregate"
    assert SPECS["obi"].price_mode == "offer"


def test_get_check_returns_callable():
    check = get_check("obi")
    assert callable(check)


def test_ean_anchor_baked_into_no_url_secret():
    # URLs müssen die recon-verifizierten Produkt-IDs enthalten
    assert "204374464" in SPECS["idealo"].url
    assert "12356554" in SPECS["hornbach"].url
    assert "8620890" in SPECS["obi"].url
    assert "31934233" in SPECS["bauhaus"].url
    assert "1425543" in SPECS["hagebau"].url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sources_registry.py -v`
Expected: FAIL with `ImportError: cannot import name 'SPECS'`

- [ ] **Step 3: Write the implementation**

`src/sources/__init__.py`:
```python
from .base import SourceSpec, check_jsonld

SPECS: dict[str, SourceSpec] = {
    "idealo": SourceSpec(
        "idealo",
        "https://www.idealo.de/preisvergleich/OffersOfProduct/204374464_-portasplit-3-5-kw-midea.html",
        price_mode="aggregate",
    ),
    "hornbach": SourceSpec(
        "hornbach",
        "https://www.hornbach.de/p/klimasplitgeraet-midea-portasplit-12-000-btu-105-m-weiss/12356554/",
    ),
    "obi": SourceSpec(
        "obi",
        "https://www.obi.de/p/8620890/midea-mobile-split-klimaanlage-portasplit",
    ),
    "bauhaus": SourceSpec(
        "bauhaus",
        "https://www.bauhaus.info/klimaanlagen/midea-klimasplitgeraet-portasplit-12000-btu/p/31934233",
    ),
    "hagebau": SourceSpec(
        "hagebau",
        "https://www.hagebau.de/p/midea-klimaanlage-portasplit-12000-btu-anV1425543/",
    ),
}


def get_check(name: str):
    if name == "toom":
        from . import toom

        return toom.check
    spec = SPECS[name]
    return lambda client: check_jsonld(client, spec)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sources_registry.py -v`
Expected: PASS (4 tests). `get_check("obi")` ist callable; `get_check("toom")` wird erst nach Task 5 importierbar — hier nicht getestet.

- [ ] **Step 5: Commit**

```bash
git add src/sources/__init__.py tests/test_sources_registry.py
git commit -m "feat: source registry with 5 recon-verified JSON-LD sources"
```

---

### Task 5: toom Custom Source

**Files:**
- Create: `src/sources/toom.py`
- Test: `tests/test_toom.py`

**Interfaces:**
- Consumes: `src.sources.base.fetch`, `src.jsonld.*`, `src.models.Offer`
- Produces:
  - `src.sources.toom.NAME = "toom"`, `src.sources.toom.URL`
  - `parse(html: str) -> Offer | None` (sichtbarer Preis via Regex, `ean=None`, Verfügbarkeit aus JSON-LD)
  - `check(client) -> Offer | None`

**Begründung Sonderfall (Recon):** toom liefert `gtin13` == interne Artikelnr. (unbrauchbar als EAN) und einen falschen JSON-LD-Preis (799 statt sichtbar 699). Darum: Preis aus sichtbarem Text, `ean=None` → Identität später über Name-Match (Task 6).

- [ ] **Step 1: Write the failing test**

`tests/test_toom.py`:
```python
from src.sources.toom import parse

TOOM_HTML = """
<html><body>
<span class="price">699,00 €</span>
<script type="application/ld+json">
{"@type":"Product","name":"Midea Mobiles Klimagerät 'PortaSplit' 12000 BTU/h",
 "sku":"9350668","gtin13":"9350668",
 "offers":{"@type":"Offer","availability":"http://schema.org/OutOfStock","price":"799"}}
</script>
</body></html>
"""


def test_toom_uses_visible_price_not_jsonld_price():
    offer = parse(TOOM_HTML)
    assert offer.price == 699.0  # NICHT 799 aus dem JSON-LD
    assert offer.available is False
    assert offer.ean is None  # gtin13 ist unbrauchbar -> Name-Match


def test_toom_missing_availability_is_failure():
    html = '<script type="application/ld+json">{"@type":"Product","name":"x","offers":{"price":1}}</script>'
    assert parse(html) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_toom.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.sources.toom'`

- [ ] **Step 3: Write the implementation**

`src/sources/toom.py`:
```python
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
    price = float(f"{m.group(1)}.{m.group(2)}") if m else None
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_toom.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/sources/toom.py tests/test_toom.py
git commit -m "feat: toom custom source (visible price, name-match, unreliable gtin)"
```

---

### Task 6: Product Matching & Alert Filter

**Files:**
- Create: `src/filter.py`
- Test: `tests/test_filter.py`

**Interfaces:**
- Consumes: `src.models.Offer`, `src.config.Config`, `src.config.ProductConfig`
- Produces:
  - `matches_product(offer: Offer, p: ProductConfig) -> bool` (EAN-Match falls `offer.ean` gesetzt, sonst Name-Match)
  - `should_alert(offer: Offer, cfg: Config) -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_filter.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_filter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.filter'`

- [ ] **Step 3: Write the implementation**

`src/filter.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_filter.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/filter.py tests/test_filter.py
git commit -m "feat: product identity matching and alert filter"
```

---

### Task 7: State & Dedupe

**Files:**
- Create: `src/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `new_source_state() -> dict` → `{"alerted": False, "alert_price": None, "fail_count": 0, "warned": False}`
  - `load_state(path: str) -> dict` (fehlt/kaputt → `{"sources": {}}`)
  - `save_state(path: str, state: dict) -> None`
  - `is_new_alert(prev: dict | None, price: float) -> bool` (True wenn vorher nicht alarmiert ODER Preis gesunken)

- [ ] **Step 1: Write the failing test**

`tests/test_state.py`:
```python
from src.state import is_new_alert, load_state, new_source_state, save_state


def test_load_missing_returns_empty(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) == {"sources": {}}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    save_state(path, {"sources": {"obi": new_source_state()}})
    loaded = load_state(path)
    assert loaded["sources"]["obi"]["alerted"] is False


def test_is_new_alert_first_time():
    assert is_new_alert(None, 749.0) is True
    assert is_new_alert({"alerted": False, "alert_price": None}, 749.0) is True


def test_is_new_alert_suppresses_repeat_same_price():
    prev = {"alerted": True, "alert_price": 749.0}
    assert is_new_alert(prev, 749.0) is False


def test_is_new_alert_fires_on_price_drop():
    prev = {"alerted": True, "alert_price": 749.0}
    assert is_new_alert(prev, 699.0) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.state'`

- [ ] **Step 3: Write the implementation**

`src/state.py`:
```python
import json
import os


def new_source_state() -> dict:
    return {"alerted": False, "alert_price": None, "fail_count": 0, "warned": False}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"sources": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return {"sources": {}}
    if "sources" not in data:
        data["sources"] = {}
    return data


def save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def is_new_alert(prev: dict | None, price: float) -> bool:
    if prev is None or not prev.get("alerted"):
        return True
    prev_price = prev.get("alert_price")
    return prev_price is None or price < prev_price
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/state.py tests/test_state.py
git commit -m "feat: state persistence and alert dedupe"
```

---

### Task 8: Telegram Notification

**Files:**
- Create: `src/notify.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `httpx` (injizierbar als `client` für Tests)
- Produces:
  - `send_telegram(token, chat_id, text, *, button_text=None, button_url=None, client=None) -> response`

- [ ] **Step 1: Write the failing test**

`tests/test_notify.py`:
```python
from src.notify import send_telegram


class _FakeResp:
    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResp()


def test_send_telegram_builds_payload_with_button():
    client = _FakeClient()
    send_telegram(
        "TOKEN", "123", "Verfügbar!",
        button_text="Zum Shop", button_url="https://shop.example/p",
        client=client,
    )
    call = client.calls[0]
    assert "botTOKEN/sendMessage" in call["url"]
    assert call["json"]["chat_id"] == "123"
    assert call["json"]["text"] == "Verfügbar!"
    kb = call["json"]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["url"] == "https://shop.example/p"


def test_send_telegram_without_button_has_no_markup():
    client = _FakeClient()
    send_telegram("TOKEN", "123", "Health-Warnung", client=client)
    assert "reply_markup" not in client.calls[0]["json"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_notify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.notify'`

- [ ] **Step 3: Write the implementation**

`src/notify.py`:
```python
import httpx

_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(token, chat_id, text, *, button_text=None, button_url=None, client=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": button_text or "Zum Shop", "url": button_url}]]
        }
    c = client or httpx
    resp = c.post(_API.format(token=token), json=payload, timeout=15)
    resp.raise_for_status()
    return resp
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_notify.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/notify.py tests/test_notify.py
git commit -m "feat: Telegram notification with inline buy button"
```

---

### Task 9: Health-Check

**Files:**
- Create: `src/health.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Consumes: nothing (Callback `on_warn` wird injiziert)
- Produces:
  - `record_failure(src_state: dict, threshold: int, on_warn) -> None` (zählt hoch, ruft `on_warn()` einmalig bei Erreichen der Schwelle)
  - `record_success(src_state: dict) -> None` (reset)

- [ ] **Step 1: Write the failing test**

`tests/test_health.py`:
```python
from src.health import record_failure, record_success
from src.state import new_source_state


def test_warns_once_at_threshold():
    state = new_source_state()
    warns = []
    on_warn = lambda: warns.append(1)
    record_failure(state, 3, on_warn)
    record_failure(state, 3, on_warn)
    assert warns == []          # noch unter Schwelle
    record_failure(state, 3, on_warn)
    assert warns == [1]         # bei 3 genau einmal
    record_failure(state, 3, on_warn)
    assert warns == [1]         # kein erneuter Spam


def test_success_resets_counter_and_warned():
    state = new_source_state()
    on_warn = lambda: None
    record_failure(state, 1, on_warn)
    record_success(state)
    assert state["fail_count"] == 0
    assert state["warned"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.health'`

- [ ] **Step 3: Write the implementation**

`src/health.py`:
```python
def record_failure(src_state: dict, threshold: int, on_warn) -> None:
    src_state["fail_count"] = src_state.get("fail_count", 0) + 1
    if src_state["fail_count"] >= threshold and not src_state.get("warned"):
        on_warn()
        src_state["warned"] = True


def record_success(src_state: dict) -> None:
    src_state["fail_count"] = 0
    src_state["warned"] = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/health.py tests/test_health.py
git commit -m "feat: health-check for broken sources (warn once at threshold)"
```

---

### Task 10: Monitor Orchestration + Entry Point

**Files:**
- Create: `src/monitor.py`, `src/run.py`
- Test: `tests/test_monitor.py`

**Interfaces:**
- Consumes: `src.filter.should_alert`, `src.state.new_source_state`, `src.state.is_new_alert`, `src.health.record_failure`, `src.health.record_success`, `src.models.Offer`
- Produces:
  - `run_once(cfg, state, get_check, notify_offer, notify_health, client) -> dict`
    - `get_check(name) -> callable(client) -> Offer | None`
    - `notify_offer(offer: Offer) -> None`, `notify_health(name: str) -> None`
  - `src.run.format_offer(offer: Offer) -> tuple[str, str]` (Text, Button-URL)
  - `src.run.main() -> None` (lädt Config/State, wirt reale Deps, speichert State)

- [ ] **Step 1: Write the failing test**

`tests/test_monitor.py`:
```python
from src.config import Config, ProductConfig
from src.models import Offer
from src.monitor import run_once

PRODUCT = ProductConfig("4048164116478", "10002085", ["portasplit"], ["12000"], ["cool"])


def _cfg(sources):
    return Config(PRODUCT, 850.0, sources, True, 2)


def _offer(name, price, available, ean="4048164116478"):
    return Offer(name, "Midea PortaSplit 12000", "https://u/" + name, price, available, False, ean)


def test_alerts_once_for_in_stock_at_good_price():
    alerts, healths = [], []
    checks = {"obi": lambda c: _offer("obi", 799.0, True)}
    state = {"sources": {}}
    run_once(_cfg(["obi"]), state, lambda n: checks[n], alerts.append, healths.append, client=None)
    assert len(alerts) == 1
    assert state["sources"]["obi"]["alerted"] is True
    # zweiter Lauf, gleicher Zustand -> kein erneuter Alarm
    run_once(_cfg(["obi"]), state, lambda n: checks[n], alerts.append, healths.append, client=None)
    assert len(alerts) == 1


def test_overpriced_does_not_alert():
    alerts = []
    checks = {"idealo": lambda c: _offer("idealo", 999.0, True)}
    run_once(_cfg(["idealo"]), {"sources": {}}, lambda n: checks[n], alerts.append, lambda n: None, None)
    assert alerts == []


def test_failed_source_triggers_health_after_threshold():
    healths = []

    def boom(c):
        raise RuntimeError("blocked")

    state = {"sources": {}}
    cfg = _cfg(["hagebau"])
    for _ in range(2):  # threshold == 2
        run_once(cfg, state, lambda n: boom, lambda o: None, healths.append, None)
    assert healths == ["hagebau"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.monitor'`

- [ ] **Step 3: Write the implementation**

`src/monitor.py`:
```python
from .filter import should_alert
from .health import record_failure, record_success
from .state import is_new_alert, new_source_state


def run_once(cfg, state, get_check, notify_offer, notify_health, client) -> dict:
    sources = state.setdefault("sources", {})
    for name in cfg.sources_enabled:
        src_state = sources.setdefault(name, new_source_state())
        try:
            offer = get_check(name)(client)
        except Exception:
            offer = None
        if offer is None:
            record_failure(src_state, cfg.health_fail_threshold,
                           lambda n=name: notify_health(n))
            continue
        record_success(src_state)
        if should_alert(offer, cfg):
            if is_new_alert(src_state, offer.price):
                notify_offer(offer)
            src_state["alerted"] = True
            src_state["alert_price"] = offer.price
        else:
            src_state["alerted"] = False
            src_state["alert_price"] = None
    return state
```

`src/run.py`:
```python
import os

import httpx

from .config import load_config
from .models import Offer
from .monitor import run_once
from .notify import send_telegram
from .sources import get_check
from .state import load_state, save_state

CONFIG_PATH = "config.yaml"
STATE_PATH = "state.json"


def format_offer(offer: Offer) -> tuple[str, str]:
    pickup = " · 🏬 Abholung" if offer.pickup_only else ""
    price = f"{offer.price:.2f} €" if offer.price is not None else "Preis unbekannt"
    text = (
        "🟢 <b>Midea PortaSplit verfügbar!</b>\n"
        f"{offer.source} — <b>{price}</b>{pickup}"
    )
    return text, offer.url


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    cfg = load_config(CONFIG_PATH)
    state = load_state(STATE_PATH)

    def notify_offer(offer: Offer) -> None:
        text, url = format_offer(offer)
        send_telegram(token, chat_id, text, button_text="🛒 Zum Shop", button_url=url)

    def notify_health(name: str) -> None:
        send_telegram(
            token, chat_id,
            f"⚠️ Quelle <b>{name}</b> reagiert mehrfach nicht. Bitte Scraper prüfen.",
        )

    with httpx.Client() as client:
        state = run_once(cfg, state, get_check, notify_offer, notify_health, client)
    save_state(STATE_PATH, state)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS (alle Tests aus Task 1–10)

- [ ] **Step 6: Commit**

```bash
git add src/monitor.py src/run.py tests/test_monitor.py
git commit -m "feat: monitor orchestration and entry point"
```

---

### Task 11: GitHub Actions Workflow + Go-Live

**Files:**
- Create: `.github/workflows/monitor.yml`
- Modify: `README.md` (Setup-Abschnitt mit echten Schritten)

**Interfaces:**
- Consumes: `src.run.main` (via `python -m src.run`), GitHub Secrets `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Produces: laufender 5-Min-Cron

- [ ] **Step 1: Write the workflow**

`.github/workflows/monitor.yml`:
```yaml
name: PortaSplit Monitor
on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch: {}
permissions:
  contents: read
concurrency:
  group: portasplit-monitor
  cancel-in-progress: false
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - name: Restore monitor state
        uses: actions/cache@v4
        with:
          path: state.json
          key: portasplit-state-${{ github.run_id }}
          restore-keys: |
            portasplit-state-
      - name: Run monitor
        run: python -m src.run
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

- [ ] **Step 2: Local dry-run against live sites (manuelle Verifikation)**

Run (lokal, mit gesetzten Env-Vars):
```bash
TELEGRAM_BOT_TOKEN=<token> TELEGRAM_CHAT_ID=<chat_id> python -m src.run
```
Expected: Lauf ohne Crash. `state.json` wird erzeugt. Bei aktuellem Markt sollten **OBI** (799,99 €, InStoreOnly) und ggf. **toom** als Alarm kommen; überteuerte (Idealo 999 €) NICHT. **Hornbach/Hagebau:** Falls eine dieser Quellen kein `availability`-Feld liefert oder Hagebau durch Friendly Captcha blockiert wird, erscheint nach `health_fail_threshold` Läufen die ⚠️-Health-Meldung — dann diese Quelle prüfen (Selektor/Block) oder via `sources_enabled` vorerst deaktivieren.

- [ ] **Step 3: Verifikation der Verfügbarkeits-Felder (Recon-Lücke schließen)**

Für **hornbach** und **hagebau** den tatsächlichen `offers.availability`-Wert prüfen:
```bash
python -c "import httpx; from src.sources import SPECS; from src.sources.base import fetch, parse_jsonld_source; c=httpx.Client(); print(parse_jsonld_source(fetch(c, SPECS['hornbach'].url), SPECS['hornbach']))"
```
Expected: ein `Offer(...)` (nicht `None`). Ist es `None`, fehlt das Verfügbarkeits-Feld → der Silent-OOS-Schutz hat korrekt gegriffen; dann für diese Quelle die Verfügbarkeit aus einem alternativen HTML-Marker ableiten (separater Folge-Task) oder Quelle deaktivieren. **Niemals stillschweigend „immer nicht verfügbar" laufen lassen.**

- [ ] **Step 4: Update README setup section**

In `README.md` den Abschnitt „Setup" ersetzen durch:
```markdown
## Setup

1. Telegram-Bot bei [@BotFather](https://t.me/botfather) anlegen → `TELEGRAM_BOT_TOKEN`.
2. Chat-ID ermitteln: dem Bot eine Nachricht schicken, dann
   `https://api.telegram.org/bot<TOKEN>/getUpdates` öffnen → `chat.id`.
3. In GitHub: **Settings → Secrets and variables → Actions** zwei Secrets anlegen:
   `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. Workflow läuft automatisch alle 5 Min; manuell testen über **Actions → PortaSplit Monitor → Run workflow**.

Konfiguration in `config.yaml` (Preisgrenze, aktive Quellen).
```

- [ ] **Step 5: Commit & push**

```bash
git add .github/workflows/monitor.yml README.md
git commit -m "feat: GitHub Actions 5-min cron workflow and go-live docs"
git push origin main
```

- [ ] **Step 6: Aktivierung (durch Nutzer)**

GitHub-Secrets setzen (Schritt 4 README), dann **Actions → Run workflow** für einen ersten manuellen Lauf. Cron läuft danach automatisch.

---

## Self-Review

**1. Spec coverage:**
- Produkt-Identität/EAN → Task 4 (URLs mit IDs), Task 6 (`matches_product` EAN+Name) ✅
- Markt-Lage/Preisfilter (≤850) → Task 6 `should_alert` ✅
- Add-to-Cart/Deeplink (v1 = Direktlink) → Task 10 `format_offer` Button = `offer.url` ✅
- 6 Quellen mit recon-Signalen → Task 3/4 (generisch) + Task 5 (toom) ✅
- Abholung zählt (`InStoreOnly`) → Task 2 `availability_state` ✅
- JSON-LD-Detection → Task 2/3 ✅
- Telegram-Notify → Task 8 ✅
- GitHub Actions Cron 5 Min → Task 11 ✅
- State/Dedupe → Task 7 ✅
- Health-Check (Silent-OOS-Schutz) → Task 3 (None bei fehlender Verfügbarkeit) + Task 9 ✅
- Tests gegen Fixtures → jede Task hat TDD-Tests mit eingebetteten HTML-Snippets ✅
- Keine Secrets im Code → Task 10 (env), Task 11 (GitHub Secrets) ✅
- toom-Eigenheiten (Preis/EAN) → Task 5 ✅
- Hagebau Captcha-Risiko → Task 11 Step 2/3 (Health-Fallback dokumentiert) ✅

**2. Placeholder scan:** Kein TBD/TODO im Code. Die einzige bewusst offene Stelle (Hornbach/Hagebau Verfügbarkeits-Feld) ist als ausführbarer Verifikationsschritt (Task 11 Step 3) mit klarer Wenn-dann-Handlung formuliert, nicht als Platzhalter — und durch den Silent-OOS-Schutz abgesichert.

**3. Type consistency:** `Offer`-Felder (source, title, url, price, available, pickup_only, ean) konsistent über alle Tasks. `SourceSpec` (name, url, price_mode, trust_ean) konsistent Task 3/4. `run_once`-Signatur identisch in Task 10 Test & Impl. `new_source_state`-Keys (alerted, alert_price, fail_count, warned) konsistent in Task 7/9/10.

**v2 (nicht Teil dieses Plans):** Geizhals-Aggregator, Add-to-Cart-Deeplinks, feingranulare Hamburg-Filialabfrage (inkl. toom-Filialbestand), MediaMarkt/Amazon via Playwright.
