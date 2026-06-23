from .filter import should_alert
from .health import record_failure, record_success
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
