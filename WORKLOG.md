# WORKLOG — PortaSplit Monitor v2 (echte Verfügbarkeit / Filialbestände)

Goal: see [GOAL.md](GOAL.md). User base location: Hamburg, 22303 (Barmbek).
"Umgebung" = Märkte im Umkreis ~30 km (Barmbek, Wandsbek, Altona, Norderstedt, Henstedt-Ulzburg, …).

## Iteration-Backlog (priorisiert nach Machbarkeit + HH-Relevanz)
- [ ] **It.1 — OBI Filialbestand HH**: Storefinder/`availability`-API entdecken, HH-Markt-ID(s) finden, Scraper, Chrome-Verify.
- [ ] **It.2 — toom**: (a) httpx-Problem fixen (liefert kein JSON-LD → evtl. Header/Playwright/anderer Endpunkt); (b) „Verfügbar in {Markt}" für HH-Märkte parsen.
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
- v2-Arbeit beginnt mit It.1 (OBI Filialbestand).

## Next Action
It.1: OBI-Storefinder/Availability-API via Chrome reverse-engineeren (HH-Markt wählen, Netzwerk-Call
mit Produkt-SKU 8620890 + Markt-ID erfassen), Antwortformat dokumentieren.
