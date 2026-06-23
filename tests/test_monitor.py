from src.config import Config, ProductConfig
from src.models import Offer
from src.monitor import run_once

PRODUCT = ProductConfig(
    name="Midea PortaSplit 3,5 kW",
    ean="4048164116478",
    model_no="10002085",
    max_price_eur=850.0,
    match_require_all=["portasplit"],
    match_require_any=["12000"],
    match_exclude_any=["cool"],
)


def _cfg(sources):
    return Config([PRODUCT], sources, True, 2)


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
