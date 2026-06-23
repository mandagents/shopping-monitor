"""Local self-verify: run every enabled source and print per-source results.

Runs from THIS machine's IP (residential) — reaches more shops than the CI
datacenter IP. Use to verify scrapers still parse correctly end-to-end.

    .venv/bin/python tools/selfcheck.py
"""
import sys
import time

import httpx

sys.path.insert(0, ".")
from src.config import load_config
from src.filter import match_product, should_alert
from src.sources import get_check


def main() -> None:
    cfg = load_config("config.yaml")
    print(f"Sources: {', '.join(cfg.sources_enabled)}\n")
    rows = []
    with httpx.Client() as client:
        for name in cfg.sources_enabled:
            t0 = time.time()
            err = None
            offer = None
            try:
                offer = get_check(name)(client)
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {str(e)[:140]}"
            dt = time.time() - t0
            if offer is None:
                print(f"[{name:16}] ❓ no offer ({err or 'returned None'})  ({dt:.1f}s)")
                rows.append((name, None, None, None, False))
                continue
            prod = match_product(offer, cfg.products)
            alert = should_alert(offer, cfg.products)
            pname = prod.name if prod else "—(no product match)"
            flag = "🟢 ALERT" if alert else ("🟡 avail" if offer.available else "⚪ n/a")
            price = f"{offer.price:.2f}€" if offer.price is not None else "?€"
            print(
                f"[{name:16}] {flag}  available={offer.available} {price} "
                f"pickup={offer.pickup_only}  ({dt:.1f}s)\n"
                f"{'':18}  → {pname}\n"
                f"{'':18}  title: {offer.title[:90]}"
            )
            rows.append((name, offer.available, offer.price, alert, True))

    ok = [r[0] for r in rows if r[4]]
    bad = [r[0] for r in rows if not r[4]]
    alerts = [r[0] for r in rows if r[3]]
    print("\n=== SUMMARY ===")
    print(f"readable ({len(ok)}): {', '.join(ok) or '—'}")
    print(f"failed   ({len(bad)}): {', '.join(bad) or '—'}")
    print(f"would alert ({len(alerts)}): {', '.join(alerts) or '—'}")


if __name__ == "__main__":
    main()
