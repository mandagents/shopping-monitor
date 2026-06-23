from src.config import Config, ProductConfig
from src.monitor import run_woklima
from src.sources import woklima

PRODUCT = ProductConfig(
    name="Midea PortaSplit 3,5 kW", ean="4048164116478", model_no="",
    max_price_eur=850.0, match_require_all=["portasplit"],
    match_require_any=["12000"], match_exclude_any=["cool"],
)


def _cfg():
    return Config([PRODUCT], [], True, 2, woklima_enabled=True, woklima_country="de")


def _data(bauhaus="sold_out", hornbach="available", ali_price="696,70 €"):
    return {
        "product": "Midea PortaSplit",
        "aliexpress": {"price": ali_price, "url": "https://s.click.aliexpress.com/e/x"},
        "retailers": [
            {"slug": "bauhaus", "name": "Bauhaus", "status": bauhaus,
             "status_label": "ausverkauft" if bauhaus == "sold_out" else "verfügbar",
             "price": "749,00 €", "product_url": "https://www.bauhaus.info/p/1"},
            {"slug": "hornbach", "name": "Hornbach", "status": hornbach,
             "status_label": "verfügbar" if hornbach == "available" else "ausverkauft",
             "price": "749,00 €", "product_url": "https://www.hornbach.de/p/2"},
            {"name": "NoSlug", "status": "available", "price": "1,00 €"},  # ignored
        ],
    }


# --- build_snapshot ---

def test_build_snapshot_keeps_meaningful_fields_and_skips_slugless():
    snap = woklima.build_snapshot(_data())
    assert set(snap["retailers"]) == {"bauhaus", "hornbach"}
    assert snap["retailers"]["bauhaus"]["status"] == "sold_out"
    assert snap["retailers"]["hornbach"]["price"] == "749,00 €"
    assert snap["aliexpress"] == {"price": "696,70 €", "url": "https://s.click.aliexpress.com/e/x"}


def test_build_snapshot_drops_aliexpress_without_price():
    snap = woklima.build_snapshot({"retailers": [], "aliexpress": {"url": "x"}})
    assert snap["aliexpress"] is None


# --- diff_snapshots ---

def test_diff_no_baseline_is_empty():
    assert woklima.diff_snapshots(None, woklima.build_snapshot(_data())) == []


def test_diff_no_change_is_empty():
    snap = woklima.build_snapshot(_data())
    assert woklima.diff_snapshots(snap, snap) == []


def test_diff_detects_status_flip():
    old = woklima.build_snapshot(_data(bauhaus="sold_out"))
    new = woklima.build_snapshot(_data(bauhaus="available"))
    msgs = woklima.diff_snapshots(old, new)
    assert any("Bauhaus" in m and "🟢" in m for m in msgs)


def test_diff_detects_price_change():
    old = woklima.build_snapshot(_data(ali_price="696,70 €"))
    new = woklima.build_snapshot(_data(ali_price="650,00 €"))
    msgs = woklima.diff_snapshots(old, new)
    assert any("AliExpress" in m and "650,00" in m for m in msgs)


def test_diff_detects_new_and_removed_retailer():
    old = woklima.build_snapshot(_data())
    reduced = _data()
    reduced["retailers"] = [reduced["retailers"][0]]  # only bauhaus
    new = woklima.build_snapshot(reduced)
    msgs = woklima.diff_snapshots(old, new)
    assert any("Hornbach" in m and "nicht mehr" in m for m in msgs)


# --- summarize ---

def test_summarize_lists_retailers_and_cool_deal():
    text = woklima.summarize(woklima.build_snapshot(_data()))
    assert "Hornbach" in text and "Bauhaus" in text
    assert "AliExpress (Cool 2,35 kW)" in text


# --- run_woklima orchestration ---

def test_run_woklima_baseline_then_change():
    base, change, health = [], [], []
    state = {"sources": {}}
    # first run: baseline only
    state = run_woklima(_cfg(), state, lambda c: _data(bauhaus="sold_out"),
                        change.append, base.append, health.append)
    assert len(base) == 1 and change == [] and health == []
    assert state["sources"]["woklima"]["snapshot"]["retailers"]["bauhaus"]["status"] == "sold_out"
    # second run: bauhaus flips -> change notification
    state = run_woklima(_cfg(), state, lambda c: _data(bauhaus="available"),
                        change.append, base.append, health.append)
    assert len(base) == 1 and len(change) == 1
    assert "Bauhaus" in change[0]


def test_run_woklima_no_change_is_silent():
    base, change = [], []
    state = run_woklima(_cfg(), {"sources": {}}, lambda c: _data(),
                        change.append, base.append, lambda n: None)
    state = run_woklima(_cfg(), state, lambda c: _data(),
                        change.append, base.append, lambda n: None)
    assert len(base) == 1 and change == []


def test_run_woklima_fetch_failure_warns_after_threshold():
    health = []

    def boom(country):
        raise RuntimeError("blocked")

    state = {"sources": {}}
    for _ in range(2):  # threshold=2
        state = run_woklima(_cfg(), state, boom, lambda b: None, lambda b: None, health.append)
    assert health == ["woklima"]
    assert state["sources"]["woklima"]["fail_count"] == 2
