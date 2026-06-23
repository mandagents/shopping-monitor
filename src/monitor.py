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
        if should_alert(offer, cfg.products):
            if is_new_alert(src_state, offer.price):
                notify_offer(offer)
            src_state["alerted"] = True
            src_state["alert_price"] = offer.price
        else:
            src_state["alerted"] = False
            src_state["alert_price"] = None
    return state
