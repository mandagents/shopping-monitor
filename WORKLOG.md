# WORKLOG — PortaSplit Monitor v2 (echte Verfügbarkeit / Filialbestände)

Goal: see [GOAL.md](GOAL.md). User base location: Hamburg, 22303 (Barmbek).
"Umgebung" = Märkte im Umkreis ~30 km (Barmbek, Wandsbek, Altona, Norderstedt, Henstedt-Ulzburg, …).

## Iteration-Backlog (priorisiert nach Machbarkeit + HH-Relevanz)
- [~] **It.1 — OBI Filialbestand HH**: ✅ **API gefunden + verifiziert!** `GET https://www.obi.de/api/pdp/v1/stock/{SKU}?storeIds={ids}`
  → JSON `[{"storeId","availableQuantity"}]`, httpx-tauglich (KEIN Playwright). HH-Markt-IDs (nächste zu 22303):
  `281,497,420,040,483,443,377,545,253,569` (Eppendorf 5,9km, Altona 8,9km, Norderstedt, Glinde, Bergedorf,
  Harburg, Neugraben, Buchholz …). Aktuell alle qty 0 = „zzt. nicht auf Lager" (deckt sich mit Live-Panel).
  Preis kommt aus der Produktseiten-JSON-LD (799,99). → Scraper `obi_stores` bauen (in Arbeit).
- [x] **It.2 — toom**: DIAGNOSTIZIERT → React/CSR, Product-JSON-LD client-injiziert, Verfügbarkeit nicht in roh-HTML, kein separater API-Call (Daten in Hydration-Blob). httpx kann's nicht zuverlässig. → **toom in config DEAKTIVIERT** (stoppt Dauer-Health-Warnung), für Playwright-Track (v2) vorgemerkt. Aktive Quellen jetzt: idealo, obi, bauhaus, hagebau.
- [ ] **It.3 — Bauhaus Click&Collect HH** (Wandsbek): Filialbestand-Endpunkt, Scraper, Chrome-Verify.
- [ ] **It.4 — idealo robuster**: 503/Rate-Limit (Retry/Backoff, Headers) — cross-cutting.
- [ ] **It.5 — Deep-/Add-to-Cart-Links** pro Shop in der Telegram-Nachricht.
- [ ] **It.6 — Hornbach** erneut prüfen (Cloudflare; nur falls nicht-blockierter Pfad existiert).
- [ ] **GATE — MediaMarkt/Saturn, Amazon**: bot-geschützt → Nutzer fragen, bevor Zeit investiert wird.

## Evidence / Findings
- 2026-06-22: Feasibility-Probe OBI-Produktseite (8620890): UI-Cues „markt/im markt/reservieren/abholung";
  API-Hinweise `/discover/storefinder-fragment/public/`, Klassen `availability-block`/`hd-availability`/
  `availability-indicator`. → OBI-Filialbestand über Storefinder + interne Availability-API erreichbar.
- 2026-06-22: `InStoreOnly` als Verfügbarkeit verworfen (OBI/Hagebau senden es als statisches Katalog-Flag) —
  daher braucht echter Filialbestand einen anderen, markt-spezifischen Datenpfad.

## Current State
- Bot live (Actions, 5-Min, public repo). 0 False Positives nach InStoreOnly-Fix.
- It.1 (OBI) angefangen: **Filialbestand lädt NICHT beim Seitenaufruf** — Initial-Netzwerk ist nur
  Tracking (DoubleClick/Pinterest/DynamicYield/Exponea/Instana/baqend), KEIN Availability-Call.
  → echter Bestand kommt erst nach Auswahl eines „Mein Markt" (HH) via interner API.

## Approach-Entscheidung (2026-06-22)
- **API-first**: pro Shop die markt-spezifische Stock-API nachbauen (httpx-tauglich, leichtgewichtig).
  Playwright (Headless-Browser auf Actions) nur als Fallback, wenn ein Shop ohne JS/Bot-Schutz nicht
  geht — und nur nach Rücksprache (ändert die Actions-Infra).
- **Re-Priorisierung**: zuerst schnelle, robuste Online-Abdeckung (idealo/toom fixen + 2–3 weitere
  ehrliche-`InStock`-Shops), parallel der harte Filial-Track (OBI HH).

## DONE
- ✅ **It.1 — OBI Filialbestand HH**: `obi_stores` gebaut, getestet (56/56), live verifiziert (alle HH-Märkte
  qty 0 → kein Alarm, Preis 799,99). Alarmiert mit „🏬 Abholung", sobald ein HH-Markt qty>0 hat. Commit 7c5a4d4.
- **Strategischer Lernpunkt:** Shop-interne Stock-JSON-APIs (`/api/pdp/v1/stock/{sku}?storeIds=`) sind httpx-tauglich
  → Filial-Track braucht KEIN Playwright (zumindest OBI). Muster auf Bauhaus/Hagebau/toom übertragen.

## Feasibility-Matrix Filialbestand (Reverse-Engineering-Runde, 2026-06-22)
Methode: Chrome `performance.getEntriesByType('resource')` → API finden → httpx-Verify.
| Shop | Mechanismus | httpx? | Weg |
|---|---|---|---|
| **OBI** | offene REST `/api/pdp/v1/stock/{sku}?storeIds=` | ✅ | GELIEFERT (obi_stores) |
| Bauhaus | `/api/product-availability/availability-detail/{id}` hinter **Cloudflare** (403, `__cf_bm`) | ❌ | Playwright (CI-Cloudflare-Risiko) |
| MediaMarkt | **GraphQL** `/api/v1/graphql` + Bot-Schutz | ❌ | Playwright (riskant) |
| Hagebau | **Friendly Captcha** | ❌ | Playwright (riskant) |
| toom | CSR React, kein Bot-Schutz, keine eingebettete/offene API | ⚠️ | **Playwright (viabel, kein Block)** |
→ Lesson: nur OBI hat eine offene, CI-freundliche API. Rest = bot-geschützt/CSR.

## DONE (Goal-Session 2)
- ✅ **obi_stores** (offene OBI-Stock-API) — echter HH-Filialbestand, httpx, CI-tauglich.
- ✅ **toom_stores** (Playwright) — toom HH-Wandsbek-Markt gerendert, echte Verfügbarkeit. Braucht `playwright install chromium` im CI-Workflow (User-Paste geliefert).
- ✅ **Deep-/CTA-Links** — Alerts zeigen Shop+Preis+Abholung+Titel(Markt), CTA pickup-spezifisch („Reservieren/Abholen" vs „Jetzt kaufen"), Direkt-Deep-Link-Button. Echte „Add-to-Cart"-Deeplinks bieten diese Shops öffentlich NICHT → Direkt-Produkt-/Reservierungslink ist die umsetzbare Variante.

## Wichtige Erkenntnis: Datacenter-IP-Blocking
Viele Händler blocken Datacenter/CI-IPs hart: **idealo** (persistente 503-Blockseite, 3×), **Bauhaus** (Cloudflare 403),
**Hagebau** (Friendly Captcha), **MediaMarkt** (GraphQL+Bot-Schutz). Verlässlich von CI: **OBI** (offene API) + **toom** (Playwright, kein Block).
Ob GitHub-Runner-IPs weniger geblockt sind als die Sandbox → zeigt nur der CI-Health-Check (daher nichts vorschnell deaktiviert).

## DONE (Goal-Session 2, Forts.)
- ✅ **bauhaus_stores** (Playwright, Cloudflare-Bypass via XHR-Intercept der `purchasability`-API, storeId 595 = Hamburg-Moorfleet).
- ✅ Damit 3 echte Filial-Quellen: **obi_stores** (offene API), **toom_stores** + **bauhaus_stores** (Playwright).
- **MediaMarkt (Elektronik):** Playwright lädt, Verfügbarkeit via GraphQL abfangbar — ABER Preis **1.499 €** (≈2× Retail).
  → Preisfilter (≤850) würde strukturell NIE alarmieren → **nicht gebaut** (YAGNI, nur Wartungslast). Saturn analog.
- **Hagebau:** Friendly Captcha → Playwright kann Captcha nicht lösen → nicht machbar.
- **idealo/bauhaus(online)/hagebau(online):** Datacenter-IP-geblockt (503/Cloudflare/Captcha) → ggf. CI-Health-Warnungen;
  Filial-Quellen (obi_stores/toom_stores/bauhaus_stores) + obi(online) sind die robusten.

## DONE (Forts.)
- ✅ **aliexpress** (Playwright) — Item 1005012500647890 (heise-Deal 569 € Versand DE). Marker-basierte Erkennung
  ("nicht verfügbar an Ihrem Standort"). Aktuell available=False (Deal abgelaufen/ausverkauft). Preis-Extraktion aus
  runParams beim Verfügbar-Zustand best-effort (unverifiziert, bis Item zurückkommt). Kein Bot-Challenge lokal;
  CI/Datacenter-IP-Block-Risiko (Health-Check fängt's). 8 Quellen aktiv, Suite 99 grün.

## woklima.de „abgeschaut" (Referenz-Monitor)
- ✅ **Hornbach reaktiviert** via Playwright (Cloudflare-Bypass, wie Bauhaus) — woklima zeigte es verfügbar.
  Liest Online-Bestellbarkeit + HH-Markt-Bestand aus gerendertem Text (Hornbach lässt `availability` im JSON-LD weg).
- ⚠️ **AliExpress NICHT übernommen**: woklimas Item (1005012383386980) ist die **„PortaSplit Cool 2,35 kW"** (Kühl-only-
  Billigvariante) — FALSCHES Produkt (per match_exclude ausgeschlossen). Integritäts-Catch; deine Original-Quelle bleibt.
- Hagebau: woklima nutzt andere URL (anP7004600334) — meine (anV1425543) ist EAN-verifiziert korrekt → behalten.
- Bestätigt: Filial-Ansatz richtig (woklima checkt bundesweit „X von Y Märkten"; ich Hamburg-fokussiert für dich).
- Amazon (B0D3PP64JS) listet woklima auch — bei mir offen (Bot-Schutz hart).

## Multi-Produkt (2 Varianten)
- ✅ Refactor auf `products`-Liste (Match Offer→Produkt per EAN/Name, je eigene Preisgrenze). 3,5 kW (EAN 4048164116478)
  vs Cool 2,35 kW (Name-Match, kein cross-match). Commit 5b5029a.
- ✅ **aliexpress_cool** (Item 1005012383386980): Cool-Variante, aktuell **available=True, 696,70 €** → würde alarmieren!
  (Preis via Seitentext-Heuristik, da AliExpress kein runParams mehr embedded — funktioniert aktuell, etwas fragil.)
- Cool-Abdeckung erweiterbar (weitere Shops, falls sie die Cool-Variante führen).

## Aktive Quellen (10): idealo, hornbach, obi, bauhaus, hagebau, obi_stores, toom_stores, bauhaus_stores, aliexpress, aliexpress_cool
Playwright (5): hornbach, toom_stores, bauhaus_stores, aliexpress, aliexpress_cool.

## OFFEN (User-Aktion nötig)
- ⚠️ **CI-Workflow updaten** (Playwright-Browser-Install) — Web-UI-Paste geliefert. OHNE das laufen die 3 Playwright-Quellen
  (toom_stores, bauhaus_stores, aliexpress) auf CI NICHT (je Health-Warnung).

## Next Action (Plan)
1. **Playwright-Track** bauen (öffentl. Repo = unbegrenzte Actions, Laufzeit egal). Start: **toom** (sauberer
   CSR-Kandidat, kein Block) → echter Filialbestand. CI: Playwright-Browser-Install im Workflow (User-Paste, kein Scope).
2. Opportunistisch über denselben Track: Bauhaus/MediaMarkt/Hagebau versuchen (akzeptieren, dass CI-Cloudflare ggf. blockt → Health-Check fängt's).
3. **idealo-503** robuster (Retry/Backoff) — verlässlicher Online-Gewinn.
4. **Deep-/Add-to-Cart-Links** in der Telegram-Nachricht (alle Quellen).
