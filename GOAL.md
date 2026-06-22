# GOAL — PortaSplit Monitor: echte Verfügbarkeit überall (v2)

## Outcome (beobachtbar)
Der Bot alarmiert via Telegram (mit Direkt-/Add-to-Cart-Link), sobald die **Midea PortaSplit**
(EAN `4048164116478`) **wirklich kaufbar** zum Retail-Preis (≤ 850 €) wird — inkl. **echtem
Filialbestand für Hamburg + Umgebung** (nicht das unzuverlässige `InStoreOnly`-Flag) — über
einen wachsenden Satz relevanter deutscher Händler. **Keine False Positives.**

## Baseline (Stand 2026-06-22)
- Live auf GitHub Actions (öffentliches Repo, 5-Min-Cron, autonom).
- 5 Online-Quellen: idealo (flaky/503), obi, toom (kein JSON-LD via httpx), bauhaus, hagebau.
- `InStoreOnly` wird NICHT mehr als verfügbar gewertet (war False-Positive-Quelle) → aktuell
  alarmiert nur echtes Online-`InStock` ≤ 850 €.
- Kein echter Filialbestand, keine Deep-/Add-to-Cart-Links, hornbach disabled (Cloudflare).
- Feasibility verifiziert: OBI hat Storefinder + `availability`-API → Filialbestand scrapebar.

## Constraints
- Produkt-Anker EAN `4048164116478`; MAX_PRICE 850 €.
- **Oberstes Gebot: keine False Positives** (Nutzer hatte explizit Fehlalarme; das darf nicht wieder passieren).
- Keine Secrets im Code; läuft kostenlos auf Actions (öffentliches Repo).
- Anti-Silent-Failure bleibt: unklare Verfügbarkeit → None → Health-Check, nie falsches „verfügbar".

## Non-Goals
- Kein Auto-Checkout / keine Zahlung / keine gespeicherten Zugangsdaten.
- Kein Umgehen harter Bot-Protection / CAPTCHAs (z.B. wenn MediaMarkt/Amazon nur per CAPTCHA gehen → als blockiert markieren, nicht erzwingen).

## Primary Verifier (failbar, unabhängig)
Für JEDE neue Quelle / jeden Filial-Scraper: **Chrome-Abgleich gegen die Live-Seite.**
Das Scraper-Ergebnis (verfügbar? Preis? Markt/Stadt?) MUSS mit dem übereinstimmen, was die
echte Seite im Browser zeigt. Stimmt es nicht → Verifier failt → Scraper nicht mergen.

## Supporting Checks
- Unit-Tests pro Quelle gegen gespeicherte HTML/JSON-Fixtures (InStock + OOS + Filiale).
- Live-Dry-Run muss „verfügbar" nur dann zeigen, wenn die Seite real kaufbar ist (0 False Positives).
- Deployter Actions-Lauf bleibt grün.

## Iteration Loop
1. Nächsten Shop/Mechanismus wählen (Prioritätenliste in WORKLOG.md).
2. Verfügbarkeits-/Filial-Mechanismus via Chrome entdecken (DOM, Netzwerk-API, Markt-IDs HH).
3. Scraper implementieren (TDD, Fixtures).
4. **Chrome-Verifikation**: Scraper-Output == Live-Seite (Readback/Screenshot).
5. Commit + push (nur Code/Tests — Workflow-Datei via Web-UI, kein Token-Scope).
6. WORKLOG.md fortschreiben (Evidenz, Stand, nächster Schritt).

## Autonomie / Hard Limits
Volle Autonomie: Ich entscheide **was** und **wie** selbst — Ansatz/Architektur (Playwright vs httpx),
welche Shops (auch bot-geschützte versuchen), Reihenfolge. **Keine Per-Entscheidungs-Rückfragen.**
Nur echte Hard Limits stoppen mich: Eingabe von Zugangsdaten/Secrets, sowie destruktive oder
irreversible öffentliche Aktionen ohne Freigabe. Sonst: entscheiden, umsetzen, pro Iteration berichten.

## Blocker-Standard
Externer Blocker (z.B. nur per CAPTCHA/Login, keine API) → Shop als „blocked" markieren mit
kleinstem nächsten Schritt, zum nächsten Shop weiter. Schwierigkeit allein ist kein Blocker.

## Completion Proof
Pro Shop: (a) committeter Scraper + Tests grün, (b) Chrome-Readback/Screenshot „Scraper == Live"
in WORKLOG.md. Ziel „complete", wenn der vereinbarte Hamburg-Umgebungs-Shop-Satz abgedeckt ist,
Deep-/Add-to-Cart-Links drin sind, und ein sauberer Live-Lauf 0 False Positives zeigt.
