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

## Next Action
- It.3: idealo-503 angehen (Retry/Backoff bei Datacenter-Rate-Limit).
- It.4: gleiches Stock-API-Muster für **Bauhaus** + **Hagebau** Filialbestand HH suchen (Netzwerk-Mitschnitt
  wie bei OBI) → je `*_stores`-Quelle.
- It.5: Add-to-Cart-/Deep-Links in der Telegram-Nachricht.
- Später: toom/MediaMarkt/Amazon via Playwright-Track, falls keine httpx-API.
