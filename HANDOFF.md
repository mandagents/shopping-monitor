# HANDOFF — PortaSplit Monitor (für die nächste Session)

Stand: 2026-06-23. Repo: `mandagents/shopping-monitor` (public). Bot live auf GitHub Actions (5-Min-Cron).
Siehe auch [GOAL.md](GOAL.md) + [WORKLOG.md](WORKLOG.md). Volle Detail-Historie auf Branch `feat/monitor-v1` (lokal).

## Was der Bot ist
Telegram-Alarm, wenn die Midea PortaSplit zum Retail-Preis verfügbar wird. **2 Varianten** (multi-product):
- **3,5 kW** (Wärmepumpe), EAN `4048164116478`, ≤ 850 €.
- **Cool 2,35 kW**, Name-Match (portasplit+cool+2,35), ≤ 850 €.
Architektur: `src/sources/*` (je Quelle `check()→Offer`), `filter.match_product/should_alert` (Offer→Produkt per EAN/Name),
`monitor.run_once` (mit Pro-Quelle-Logging), `notify.send_telegram`, State via Actions-Cache, Health-Check (warnt 1× nach 3 Fehlläufen).
148 Tests grün. Playwright-Browser werden im Workflow installiert (`playwright install --with-deps chromium`).

## ⚠️ KERNBEFUND: CI-Realität (verifiziert per Pro-Quelle-Log, Run 28006977466)
Auf der **kostenlosen GitHub-Actions-Datacenter-IP** funktionieren nur 4 von 10 Quellen. Die bot-geschützten
Shops blocken die Datacenter-IP — **auch Playwright/Cloudflare-Bypass scheitert auf CI** (lokal/Residential-IP geht's!).

| Quelle | CI | Grund |
|---|---|---|
| obi | ✅ | offene/erlaubte Seite |
| hagebau | ✅ | (überraschend) geht auf CI |
| obi_stores | ✅ | offene REST-Stock-API |
| toom_stores | ✅ | Playwright, toom hat keinen Bot-Schutz |
| idealo | ❌ | 503-Block (Datacenter-IP) |
| hornbach | ❌ | CI-Geo ≠ Hamburg → „HORNBACH Hamburg"-Guard greift → **fixbar: HH-Markt-Cookie setzen (wie toom/bauhaus_stores)** |
| bauhaus | ❌ | Cloudflare 403 |
| bauhaus_stores | ❌ | Cloudflare „Just a moment" — Playwright-Bypass scheitert auf CI |
| aliexpress / aliexpress_cool | ❌ | AliExpress blockt CI-IP (lokal war Cool `available=696,70 €`!) |

→ Konsequenz: Der CI-Bot überwacht aktuell zuverlässig **nur den 3,5-kW über obi/hagebau/obi_stores/toom_stores**.
Die 6 geblockten Quellen lösen je **eine** Health-Warnung aus (kein Spam danach). Die **Cool-Variante wird auf CI NICHT
gesehen** (AliExpress-Block), obwohl sie real bei ~697 € verfügbar ist.

## Nächste-Session-Aktionen (priorisiert)
1. **Entscheidung Datacenter-IP-Block** (das große Thema): Um Bauhaus, AliExpress (inkl. Cool-Variante), idealo auf CI
   zu erreichen, braucht es einen **Residential-Proxy** (z.B. über httpx/Playwright `proxy=`) oder ein anderes Hosting
   mit Residential-IP. Ohne das sind diese Shops auf Free-CI nicht scrapebar. Alternativ: diese Quellen in `config.yaml`
   `sources_enabled` **deaktivieren**, um die Health-Warnungen zu vermeiden.
2. **hornbach fixen** (geringer Aufwand, hoher Wert): in `src/sources/hornbach.py` einen Hamburg-Markt-Cookie setzen
   (Hornbach bypasste Cloudflare auf CI — es scheitert NUR am Geo-Markt). Muster: `toom_stores.py` / `bauhaus_stores.py` setzen Markt-Cookies.
3. Optional: Cool-Variante auf weitere Shops ausweiten (falls sie die Cool-Variante führen) — aber nur sinnvoll mit Proxy (s.o.).
4. Optional: AliExpress-Preis von Seitentext-Heuristik (`aliexpress*.py`) auf robusteres Signal umstellen, falls verfügbar.

## Gotchas (wichtig)
- **Token ohne `workflow`-Scope**: Workflow-Datei kann NICHT per git gepusht werden → nur per GitHub-Web-UI editieren.
- Lokales venv `.venv` (Playwright + chromium installiert). Tests: `.venv/bin/python -m pytest -q`. Browser-Tests sind env-gated.
- woklimas AliExpress-Item ist die **Cool 2,35 kW** (nicht 3,5 kW) — Varianten sauber halten (siehe match-Regeln).
- Pro-Quelle-Logging in `run_once` → CI-Logs zeigen je Quelle available/price/alert oder den Fehlergrund.
