from .filter import should_alert
from .health import record_failure, record_success
from .sources import woklima as woklima_src
from .state import is_new_alert, new_source_state


def run_once(cfg, state, get_check, notify_offer, notify_health, client) -> dict:
    sources = state.setdefault("sources", {})
    for name in cfg.sources_enabled:
        src_state = sources.setdefault(name, new_source_state())
        err = None
        try:
            offer = get_check(name)(client)
        except Exception as e:  # noqa: BLE001 - one bad source must not kill the run
            offer = None
            err = f"{type(e).__name__}: {str(e)[:120]}"
        if offer is None:
            print(f"[{name}] no offer ({err or 'returned None'}) -> health", flush=True)
            record_failure(src_state, cfg.health_fail_threshold,
                           lambda n=name: notify_health(n))
            continue
        record_success(src_state)
        alert = should_alert(offer, cfg.products)
        print(
            f"[{name}] available={offer.available} price={offer.price} "
            f"pickup={offer.pickup_only} -> {'ALERT' if alert else 'no alert'}",
            flush=True,
        )
        if alert:
            if is_new_alert(src_state, offer.price):
                notify_offer(offer)
            src_state["alerted"] = True
            src_state["alert_price"] = offer.price
        else:
            src_state["alerted"] = False
            src_state["alert_price"] = None
    return state


def run_woklima(cfg, state, fetch, notify_change, notify_baseline, notify_health) -> dict:
    """Change-radar over woklima.de's availability API.

    Not a buy-alert: woklima's "available" is a loose national-listed flag (see
    src/sources/woklima.py). We snapshot the meaningful state and report only
    *changes* (informational) so the user can verify. First run sends a one-time
    baseline summary. Fetch failures use the standard health mechanism.
    """
    src_state = state.setdefault("sources", {}).setdefault(
        "woklima", new_source_state()
    )
    try:
        data = fetch(getattr(cfg, "woklima_country", "de"))
    except Exception as e:  # noqa: BLE001 - one bad source must not kill the run
        print(f"[woklima] fetch failed ({type(e).__name__}: {str(e)[:120]}) -> health",
              flush=True)
        record_failure(src_state, cfg.health_fail_threshold, lambda: notify_health("woklima"))
        return state
    record_success(src_state)
    new_snap = woklima_src.build_snapshot(data)
    old_snap = src_state.get("snapshot")
    if old_snap is None:
        print("[woklima] baseline snapshot stored", flush=True)
        notify_baseline(woklima_src.summarize(new_snap))
    else:
        changes = woklima_src.diff_snapshots(old_snap, new_snap)
        print(f"[woklima] {len(changes)} change(s)", flush=True)
        if changes:
            notify_change("\n".join(changes))
    src_state["snapshot"] = new_snap
    return state
