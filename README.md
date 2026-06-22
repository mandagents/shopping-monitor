# Shopping Monitor — Midea PortaSplit Verfügbarkeits-Bot

Autonomer Bot, der mehrere Shops/Aggregatoren auf die Verfügbarkeit der
**Midea PortaSplit 12.000 BTU / 3,5 kW** (Wärmepumpe, Kühlen + Heizen) prüft und
bei „verfügbar zum Retail-Preis" (≤ 850 €) sofort per **Telegram** mit Kauf-Link
benachrichtigt. Lieferung **oder** Abholung in Hamburg.

- **Produkt-Anker (EAN):** `4048164116478` · Modell `10002085` (R32)
- **Ausführung:** GitHub Actions Cron, alle ~5 Min, 24/7
- **Aktion:** Benachrichtigen + Direkt-/Add-to-Cart-Link (finaler Checkout durch den Nutzer)

## Status

🟡 Design + Recon abgeschlossen — Implementierung steht aus.

Vollständiges Design: [docs/superpowers/specs/2026-06-22-klimaanlage-verfuegbarkeits-monitor-design.md](docs/superpowers/specs/2026-06-22-klimaanlage-verfuegbarkeits-monitor-design.md)

## Quellen (v1)

| Quelle | Rolle | Retail | Aktuell |
|---|---|---|---|
| Idealo | Aggregator (primär) | — | InStock, ab 999 € |
| Hornbach | Retail + HH-Abholung | 749 € | OOS |
| OBI | Retail + HH-Abholung | 799,99 € | InStoreOnly |
| toom | Retail + Filialbestand | 699 € | OOS Lieferung |
| Bauhaus | Retail + HH-Abholung | 749 € | online OOS |

## Setup (noch zu bauen)

1. Telegram-Bot via [@BotFather](https://t.me/botfather) anlegen → `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
2. Beide Werte als **GitHub Secrets** hinterlegen
3. GitHub Actions Workflow aktiviert den 5-Minuten-Cron

> Keine Login- oder Zahlungsdaten auf dem Server. Der Bot meldet nur — gekauft wird manuell.
