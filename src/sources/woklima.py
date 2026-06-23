"""woklima.de change-radar.

woklima.de aggregates Midea PortaSplit availability nationally and exposes a
clean JSON API (``/api/availability?country=de``) that returns 200 to a plain
request — no Cloudflare, no JS challenge. So it is reachable from the CI
datacenter IP, where most direct shop scrapers are blocked. That makes it a
useful early-warning radar for the bot-blocked shops and the AliExpress Cool
deal that CI cannot see directly.

IMPORTANT — why this is NOT a buy-alert source:
woklima's per-retailer ``status == "available"`` is a loose "listed with a
current price" flag, NOT a verified buy signal. Live browser checks on
2026-06-23 showed woklima reporting Hornbach (749€) and OBI (799,99€) as
"available" while in reality Hornbach was "z.Zt. nicht online bestellbar" +
"nicht im Markt vorrätig" (Hamburg) and OBI delivery was "derzeit nicht
möglich" with all Hamburg markets at qty 0. Treating that flag as a green
"verfügbar!" alert would reproduce the InStoreOnly false positives.

Therefore this module is a CHANGE RADAR: it builds a compact snapshot of
woklima's meaningful state and reports human-readable *changes* (status flips,
price moves, the AliExpress Cool deal price) as informational notifications, so
the user can go verify. The authoritative buy-signal stays with the direct
per-shop scrapers.
"""

API_URL = "https://woklima.de/api/availability"
WEBSITE_URL = "https://woklima.de/#online"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def fetch_data(client, country: str = "de") -> dict:
    resp = client.get(
        API_URL,
        params={"country": country},
        headers={"User-Agent": _UA, "Accept": "application/json"},
        timeout=20,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json()


def build_snapshot(data: dict) -> dict:
    """Compact, stable fingerprint of woklima's meaningful availability state.

    Only fields that change rarely and matter (status + price per retailer, and
    the AliExpress Cool deal price) are kept, so diffs stay low-noise.
    """
    snap: dict = {"retailers": {}, "aliexpress": None}
    for r in data.get("retailers", []) or []:
        slug = r.get("slug")
        if not slug:
            continue
        snap["retailers"][slug] = {
            "name": r.get("name") or slug,
            "status": r.get("status"),
            "label": r.get("status_label"),
            "price": r.get("price"),
            "url": r.get("product_url"),
        }
    ali = data.get("aliexpress") or {}
    if ali.get("price"):
        snap["aliexpress"] = {"price": ali.get("price"), "url": ali.get("url")}
    return snap


def _status_mark(status) -> str:
    return "🟢" if status == "available" else "🔴"


def diff_snapshots(old: dict | None, new: dict) -> list:
    """Human-readable meaningful changes from *old* to *new*.

    Returns [] when there is no baseline yet (old is falsy) or nothing changed.
    """
    if not old:
        return []
    msgs: list = []
    old_r = old.get("retailers", {})
    new_r = new.get("retailers", {})
    for slug, nr in new_r.items():
        orr = old_r.get(slug)
        name = nr.get("name") or slug
        if orr is None:
            msgs.append(f"➕ {name}: neu gelistet ({nr.get('label')}, {nr.get('price')})")
            continue
        if orr.get("status") != nr.get("status"):
            msgs.append(
                f"{_status_mark(nr.get('status'))} {name}: "
                f"{orr.get('label')} → {nr.get('label')} ({nr.get('price')})"
            )
        elif orr.get("price") != nr.get("price"):
            msgs.append(f"💶 {name}: Preis {orr.get('price')} → {nr.get('price')}")
    for slug, orr in old_r.items():
        if slug not in new_r:
            msgs.append(f"➖ {orr.get('name') or slug}: nicht mehr gelistet")

    oa = old.get("aliexpress") or {}
    na = new.get("aliexpress") or {}
    if oa.get("price") != na.get("price"):
        if na.get("price"):
            msgs.append(
                f"💶 AliExpress (Cool 2,35 kW): Preis {oa.get('price') or '—'} → {na.get('price')}"
            )
        else:
            msgs.append("➖ AliExpress (Cool 2,35 kW): Deal entfernt")
    return msgs


def summarize(snapshot: dict) -> str:
    """One-time baseline summary of woklima's current state (sent on first run)."""
    lines = []
    for r in snapshot.get("retailers", {}).values():
        mark = "🟢" if r.get("status") == "available" else "⚪"
        lines.append(f"{mark} {r.get('name')}: {r.get('label')} ({r.get('price')})")
    ali = snapshot.get("aliexpress")
    if ali and ali.get("price"):
        lines.append(f"🛒 AliExpress (Cool 2,35 kW): {ali.get('price')}")
    return "\n".join(lines)
