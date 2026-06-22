# Verfügbarkeits-Monitor: Midea PortaSplit 12.000 BTU

**Datum:** 2026-06-22
**Status:** Design abgenommen (mündlich), Recon abgeschlossen — wartet auf Spec-Review

## 1. Ziel

Ein autonomer Bot, der mehrere Shops/Aggregatoren auf die Verfügbarkeit der
**Midea PortaSplit 12.000 BTU / 3,5 kW** (Wärmepumpe, Kühlen + Heizen) prüft und
bei „verfügbar **zum Retail-Preis**" sofort eine **Telegram-Nachricht mit Kauf-Link**
schickt. Ziel: so autonom wie möglich (24/7, kein laufender Laptop nötig), ähnlich
einem Sneaker-Bot — aber mit menschlichem finalen Checkout.

Standort des Nutzers: Hamburg (22303). Lieferung **oder** Abholung gewünscht →
Hamburger Abholmärkte sind relevant.

## 2. Produkt-Identität (der Anker)

Der wichtigste Recon-Befund: Es gibt mehrere ähnlich benannte Produkte. Wir müssen
exakt das richtige treffen.

- **Zielprodukt:** Midea PortaSplit, Wärmepumpe, Kühlen + Heizen je 12.000 BTU / 3,5 kW, bis 42 m²
- **EAN / GTIN-13: `4048164116478`** ← universeller Matching-Schlüssel über alle Shops
  (bestätigt identisch bei Hornbach und Idealo)
- **Hersteller-/Modell-Nr.:** `10002085` (R32)
- **Abgrenzung (NICHT melden):** „Comfee PortaSplit **Cool**" — MPN `10002696`, 2,35 kW,
  nur Kühlen (Idealo-ID 210261557). Anderes Produkt.

**Regel:** Ein Treffer zählt nur, wenn die Quelle die EAN `4048164116478` führt ODER
(falls keine EAN verfügbar) Name + Leistungsdaten (3,5 kW, 12.000 BTU, Heizen) eindeutig passen.

## 3. Markt-Lage (Stand 2026-06-22, recon-verifiziert)

- Retail-Preis: **~749 €** (Bauhaus, Hornbach, OBI), Hagebau 849 €.
- Aktuell **fast überall „Nicht auf Lager"** zum Retail-Preis.
- In-Stock verfügbar nur bei **überteuerten** Anbietern (999–1.499 €), z.B. Idealo „ab 999 €".

→ Bestätigt den Projektzweck: Wir wollen den Alarm für **„wieder da zu Retail-Preis"**,
nicht für die teuren Daueranbieter. Der Preisfilter ist also zentral, kein Nice-to-have.

## 4. Kern-Entscheidungen (vom Nutzer abgenommen)

| Thema | Entscheidung |
|---|---|
| Aktion bei Verfügbarkeit | Benachrichtigen + **Add-to-Cart-Deeplink** (kein serverseitiger Checkout) |
| Warenkorb | 1-Tap-Deeplink öffnet den Korb **auf dem Handy des Nutzers**; sonst Direktlink zur Produktseite |
| Benachrichtigung | **Telegram-Bot** (Push mit Kauf-Button) |
| Hosting | **GitHub Actions Cron**, alle ~5 Min, gratis, 24/7 |
| Quellen-Strategie | Aggregatoren zuerst (breite Abdeckung), Direkt-Shops für HH-Abholung & saubere Deeplinks |
| Preisfilter | nur melden wenn Preis ≤ `MAX_PRICE` (= **850 €**) |
| Abholung zählt | Filialbestand/Click&Collect zählt als „verfügbar" (Hamburg priorisiert) |
| Stack | **Python** (httpx + JSON-LD-Parsing) |

## 5. Architektur

```
GitHub Actions (Cron, alle 5 Min)
   │
   ▼
[ Quellen-Module ]  ← gemeinsames Interface: check() -> list[Offer]
   ├─ idealo      (Aggregator, primär — EAN-bestätigt)
   ├─ hornbach    (Retail 749 €, HH-Abholung)
   ├─ obi         (Retail 799,99 €, InStoreOnly, HH-Abholung)
   ├─ toom        (Retail 699 €, Filialbestand, JSON-LD unsauber)
   ├─ bauhaus     (Retail 749 €, HH-Abholung Wandsbek)
   ├─ hagebau     (Retail 849 €, ⚠️ Friendly Captcha-Risiko)
   └─ … (Geizhals, MediaMarkt in v2)
   │
   ▼
[ Filter ]      → in_stock == true  UND  price <= MAX_PRICE  UND  EAN/Identität passt
   │
   ▼
[ Dedupe/State ] → bereits gemeldete (shop, price)-Kombi nicht erneut spammen
   │
   ▼
[ Telegram-Notify ] → Shop · Preis · Abholung-HH? · [Kauf-Button]
   │
   └─[ Health-Check ] → wenn Quelle X Läufe in Folge fehlschlägt → „⚠️ Quelle kaputt"-Ping
```

### 5.1 Datenmodell

```python
@dataclass
class Offer:
    source: str          # "idealo" | "hornbach" | ...
    title: str
    price: float | None  # EUR, None wenn unbekannt
    in_stock: bool
    url: str             # Produktseite oder Add-to-Cart-Deeplink
    pickup_hamburg: bool # True, wenn Filialabholung HH möglich
    matched_ean: bool    # True, wenn EAN 4048164116478 bestätigt
    cart_deeplink: str | None  # falls Shop Add-to-Cart-URL unterstützt
```

### 5.2 Quellen-Interface

Jede Quelle ist ein eigenes Modul mit `check() -> list[Offer]`. Neue Shops = neues
Modul, ohne den Rest anzufassen. Jede `check()` ist in try/except gekapselt — eine
kaputte Quelle bricht **nie** den ganzen Lauf.

## 6. Erkennungs-Technik (recon-konkretisiert)

**Primär: schema.org JSON-LD parsen** (`<script type="application/ld+json">`).
Robuster als CSS-Selektoren, überlebt Layout-Änderungen.

Pro Quelle bestätigte Signale (Recon-Stand 2026-06-22):

| Quelle | URL / ID | EAN im Markup? | JSON-LD-Signal | Verfügbarkeits-Logik | Stand jetzt |
|---|---|---|---|---|---|
| **idealo** | `/preisvergleich/OffersOfProduct/204374464_...` | ✅ `gtin13` | `AggregateOffer`: `lowPrice`, `offerCount`, `availability` | `availability==InStock` UND `lowPrice <= MAX_PRICE` | InStock, ab 999 € |
| **hornbach** | `/p/.../12356554/` (SKU 12356554) | ✅ `4048164116478` | `Product.offers.price`, `gtin13` | `offers.availability` ODER aktiver Warenkorb-Button (fehlt bei OOS) | 749 €, OOS |
| **obi** | `/p/8620890/...` (SKU 8620890) | ✅ `4048164116478` | `Product.offers.availability` (`InStoreOnly`/`InStock`), `price` | `availability != OutOfStock` UND `price <= MAX_PRICE` | **799,99 €, InStoreOnly** |
| **toom** | `/p/.../9350668` (SKU 9350668) | ❌ `gtin13`==SKU (unbrauchbar) | `availability` brauchbar; **Preis im JSON-LD falsch (799 statt 699)** | sichtbaren Preis parsen; `availability` + Filialtext („Verfügbar in …") | 699 €, OOS Lieferung, Filiale nahe HH |
| **bauhaus** | `/klimaanlagen/...-portasplit-12000-btu/p/31934233` | ✅ `4048164116478` | `Product.offers.availability`, `price` (749) | `availability != OutOfStock` ODER Filialbestand (Click&Collect, HH Wandsbek) | 749 €, online OOS |
| **hagebau** | `/p/midea-klimaanlage-portasplit-12000-btu-anV1425543/` (SKU 1425543) | ✅ `4048164116478` | `Product.offers.availability`, `price` (849) | `availability != OutOfStock` UND `price <= MAX_PRICE` | 849 €, InStoreOnly/Ausverkauft · ⚠️ **Friendly Captcha** |

**Identitäts-Check:** Wo `gtin13` vorhanden → muss `4048164116478` sein. So wird nie
die „Comfee Cool" gemeldet. **Ausnahme toom:** dort `gtin13` == interne Artikelnr. →
Match über Name (`portasplit` + `12000`/`3,5`) statt EAN; und **sichtbaren** Preis parsen,
nicht den (falschen) JSON-LD-Preis.

**Abholung als Verfügbarkeit:** Da Lieferung *oder* Abholung gewünscht ist, zählt auch
`InStoreOnly` / Filialbestand als Treffer (OBI führt es z.B. aktuell als `InStoreOnly` zu
799,99 € → mit `MAX_PRICE=850` ein gültiger Alarm). Filialbestand wird im Alarm als
„🏬 Abholung" markiert, Hamburg-Nähe priorisiert.

**Captcha-Risiko hagebau:** Die Hagebau-Produktseite liefert sauberes JSON-LD (korrekte
EAN, Preis), enthält aber **Friendly Captcha**. Ob die GitHub-Actions-IP ungehindert
durchkommt, zeigen erst die ersten Live-Läufe. Verhalten: Wird Hagebau wiederholt
blockiert, greift der Health-Check (⚠️-Ping) und wir behandeln Hagebau als reine
„im-Markt-prüfen"-Quelle (v2) statt als zuverlässige Online-Quelle. Kein blindes Vertrauen.

**Kein Headless-Browser in v1** (passt zu GitHub Actions, schnell). Realistischer
User-Agent, je Quelle 1 Request pro Lauf (höflich, kein Rate-Problem).

## 7. Benachrichtigung

Telegram-Nachricht pro **neuem** Treffer (Beispiel):

> 🟢 **Midea PortaSplit verfügbar!**
> Hornbach — **749 €** · 🏬 Abholung Hamburg möglich
> [🛒 Zum Shop / In den Warenkorb]

- Button = Add-to-Cart-Deeplink wo unterstützt, sonst Direktlink zur Produktseite.
- Telegram-Token + Chat-ID liegen in **GitHub Secrets** (nichts im Code).

## 8. State / Dedupe

- Leichtgewichtiger State (zuletzt gemeldete `(source, in_stock, price-bucket)`-Kombis).
- Persistenz via **GitHub Actions Cache** (oder committetes `state.json`).
- Erneuter Alarm nur bei Zustandswechsel (OOS→InStock) oder relevantem Preissturz —
  kein 5-Minuten-Spam bei Dauer-Verfügbarkeit.

## 9. Health-Check (gegen die typische Falle)

Klassischer Fehlermodus: Ein Scraper bricht (Seite ändert sich) und meldet still
„nie auf Lager". Schutz: Wenn eine Quelle **N Läufe in Folge** fehlschlägt (Exception
oder Parsing liefert nichts Plausibles), sendet der Bot eine
**„⚠️ Quelle Y reagiert nicht"**-Telegram-Meldung. So ist immer klar: echt ausverkauft
vs. Bot-Wartung nötig.

## 10. Konfiguration

Eine zentrale Config (Datei + GitHub Secrets):

```yaml
product:
  ean: "4048164116478"
  model_no: "10002085"
  name_contains: ["portasplit", "3,5"]   # Fallback-Match
  exclude_contains: ["cool", "2,35"]      # Comfee Cool ausschließen
max_price_eur: 850        # gelockert: fängt OBI 799,99 € mit; bewusst < 999 €
sources_enabled: ["idealo", "hornbach", "obi", "toom", "bauhaus", "hagebau"]
hamburg_pickup_priority: true
health_fail_threshold: 3  # Läufe in Folge bis Warnung
# secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

## 11. Tests (TDD)

- Pro Quelle ein Parser-Test gegen **gespeicherte HTML-Fixtures** (je ein InStock- und
  ein OutOfStock-Snapshot). Testet Erkennung ohne Netz; schlägt an, sobald ein Shop
  sein Markup ändert.
- Filter-Logik-Tests: 999 € InStock → kein Alarm; 749 € InStock → Alarm; falsche EAN → kein Alarm.
- Dedupe-Test: zweimal derselbe Zustand → nur ein Alarm.
- Smoke-Test (manuell): alle aktiven Quellen live abfragen.

## 12. Phasen

**v1 (zuerst live):**
- Quellen: **idealo** (primär-Aggregator), **hornbach**, **obi**, **toom**, **bauhaus**, **hagebau** (mit Captcha-Vorbehalt)
- JSON-LD/HTTP-Detection, EAN-Identitätscheck (toom: Name-Match), Preisfilter (`MAX_PRICE=850`)
- Abholung/Filialbestand zählt als Treffer (Hamburg priorisiert)
- Telegram-Notify mit Direktlink, GitHub Actions Cron (5 Min), Dedupe, Health-Check
- Tests gegen Fixtures (je InStock/OutOfStock-Snapshot pro Quelle)

**v2 (Ausbau):**
- **Geizhals** als Aggregator (Varianten-Disambiguierung der „Comfee"-Gruppe v233573, kein GTIN im Markup)
- Weitere Shops: MediaMarkt/Saturn, Hagebau-Regionalmärkte
- Add-to-Cart-Deeplinks (statt nur Direktlink), wo der Shop es unterstützt
- Feingranulare Hamburg-Filialabfrage (Bauhaus Wandsbek, OBI/toom HH-Märkte gezielt)
- Optional Playwright nur für bot-geschützte Seiten (Amazon, MediaMarkt)

## 13. Annahmen & offene Punkte

- `MAX_PRICE = 850 €` (vom Nutzer bestätigt; fängt OBI 799,99 € mit, bleibt < 999 €).
- Bauhaus-Filialbestand-Mechanik (Click&Collect-Endpoint) beim Bau zu fixieren; Produktseite ist bekannt (ID 31934233).
- Nutzer benötigt: Telegram-Bot via @BotFather (Token + Chat-ID). GitHub-Repo wird angelegt (Account `mandagents`).
- Scraping der Aggregatoren erfolgt höflich (1 Request/Quelle/Lauf); kein Login, keine Zahlungsdaten auf dem Server.

## 14. Nicht-Ziele (YAGNI)

- Kein serverseitiger Auto-Checkout, keine gespeicherten Zahlungs-/Login-Daten.
- Keine Captcha-Umgehung.
- Kein Multi-Produkt-Framework — bewusst auf dieses eine Gerät zugeschnitten (leicht erweiterbar).
