"""HORNBACH Hamburg availability via headless Playwright.

HORNBACH is Cloudflare-protected: plain httpx gets a JS-challenge (HTTP 403/503).
A real Playwright browser bypasses Cloudflare (HTTP 200, full page renders).

Strategy
--------
1. Navigate to the product page with a realistic User-Agent (Playwright default).
   HORNBACH defaults to a Hamburg market when accessed from a Hamburg-area IP; the
   page shows "Ist Hamburg Dein richtiger Markt?" on first visit and "HORNBACH Hamburg"
   / "MEIN MARKT" once the Hamburg market context is active.
2. Wait for the page to fully render (domcontentloaded + 4 s settle).
3. Determine availability from TWO independent text signals on the rendered page:
   a. Online/delivery: presence of "NICHT ONLINE BESTELLBAR" (case-insensitive)
      in the rendered body text → not online orderable; absence means orderable.
   b. Hamburg store pickup: "im Markt vorrätig" (preceded by optional "Z.Zt. nicht")
      in the rendered body text.  Exact patterns:
        • "im Markt vorrätig" (without "nicht") → store available
        • "nicht im Markt vorrätig" → store not available
   Note: the rendered JSON-LD offers block does NOT include an `availability` field;
   text signals are therefore the authoritative source.
4. Confirm the Hamburg market is shown (anti-silent-failure: "HORNBACH Hamburg" in text).
5. Extract price from the rendered JSON-LD offer's ``price`` field (≈749.00).

Anti-silent-failure guards
--------------------------
- Cloudflare challenge: if page title contains "Just a moment" / "Sicherheitsprüfung"
  / "403" → raise RuntimeError.
- Hamburg market not confirmed: if "HORNBACH Hamburg" not in rendered text →
  raise RuntimeError (wrong market context → results unreliable).
- Neither online signal NOR store signal found in text → return None (health alert).
- Never guess availability.

Signal semantics
----------------
- ``online_available`` True  when "NICHT ONLINE BESTELLBAR" is absent from body text.
- ``store_available``  True  when "im Markt vorrätig" appears WITHOUT "nicht" directly
  before it (i.e. the positive form).
- ``available``        True  if online_available OR store_available.
- ``pickup_only``      True  if store_available AND NOT online_available.

Signature follows the uniform ``check(client) -> Offer | None`` interface;
``client`` (httpx.Client) is intentionally ignored.
"""
from __future__ import annotations

import json
import re

from ..models import Offer
from .playwright_base import playwright_page

NAME = "hornbach"
URL = (
    "https://www.hornbach.de/p/"
    "klimasplitgeraet-midea-portasplit-12-000-btu-105-m-weiss/12356554/"
)
EAN = "4048164116478"

# The Hamburg market label HORNBACH renders once the market context is set.
_HH_MARKET_LABEL = "HORNBACH Hamburg"

_PRICE_RE = re.compile(r"(\d{2,4})[.,](\d{2})\s*€")


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable, no browser I/O)
# ---------------------------------------------------------------------------


def parse_availability_signals(body_text: str) -> tuple[bool | None, bool | None]:
    """Parse Hamburg availability from rendered body text.

    Reads two independent signals:
    1. Online orderability: presence of "nicht online bestellbar" (case-insensitive).
    2. Hamburg store pickup: "im Markt vorrätig" with/without "nicht" prefix.

    Args:
        body_text: the full rendered body text (``page.inner_text("body")``).

    Returns:
        ``(online_available, store_available)`` where each may be:
          - ``True``  / ``False`` when the signal was found and parsed.
          - ``None``  when the signal was completely absent from the text.

    This function is pure (no I/O) and can be unit-tested without a browser.
    """
    text_lower = body_text.lower()

    # --- Online signal ---
    # "Z.ZT. NICHT ONLINE BESTELLBAR" → not orderable online.
    # If this phrase is absent we treat online as available.
    if "nicht online bestellbar" in text_lower:
        online_available: bool | None = False
    elif "online bestellbar" in text_lower:
        # Positive form found (rare — future-proof)
        online_available = True
    else:
        # No online-orderability signal at all → unknown
        online_available = None

    # --- Store pickup signal ---
    # Positive: "im markt vorrätig" without "nicht" immediately before.
    # Negative: "nicht im markt vorrätig" (also "z.zt. nicht im markt vorrätig").
    if "nicht im markt vorrätig" in text_lower:
        store_available: bool | None = False
    elif "im markt vorrätig" in text_lower:
        store_available = True
    else:
        store_available = None

    return online_available, store_available


def parse_price_from_html(html: str) -> float | None:
    """Extract price from the rendered HORNBACH product page HTML.

    Prefers the Product JSON-LD ``offers[0].price`` field (Hornbach emits offers
    as a list); falls back to the first visible price pattern (e.g. ``749,00 €``).

    Args:
        html: full rendered HTML string.

    Returns:
        Price as float, or ``None`` if not found.
    """
    # --- JSON-LD: most reliable ---
    ld_re = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    for match in ld_re.finditer(html):
        try:
            block = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(block, dict) or block.get("@type") != "Product":
            continue
        offers = block.get("offers")
        # Hornbach renders offers as a list; handle both list and dict.
        if isinstance(offers, list) and offers:
            offers = offers[0]
        if isinstance(offers, dict):
            raw = offers.get("price")
            if raw is not None:
                try:
                    return float(str(raw).replace(",", "."))
                except (ValueError, TypeError):
                    pass
        break  # only first Product block

    # --- Fallback: visible price text ---
    m = _PRICE_RE.search(html)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")

    return None


# ---------------------------------------------------------------------------
# Main check() function
# ---------------------------------------------------------------------------


def check(client) -> Offer | None:  # noqa: ANN001  (client is httpx.Client, ignored)
    """Check HORNBACH Hamburg availability using Playwright.

    Navigates to the product page via Playwright (bypasses Cloudflare) and reads
    two availability signals from the rendered body text:
      1. Online orderability ("NICHT ONLINE BESTELLBAR" present/absent).
      2. Hamburg store stock ("im Markt vorrätig" / "nicht im Markt vorrätig").

    Returns ``None`` on anti-silent-failure conditions.
    Raises ``RuntimeError`` on Cloudflare block or missing Hamburg market confirmation.

    Args:
        client: httpx.Client — not used (Playwright handles all I/O).

    Returns:
        An :class:`~src.models.Offer` for HORNBACH Hamburg, or ``None``.
    """
    with playwright_page() as page:
        page.goto(URL, wait_until="domcontentloaded", timeout=45_000)
        # Allow JS/React to render availability widgets.
        page.wait_for_timeout(4_000)

        # --- Anti-silent-failure: Cloudflare challenge check ---
        title = page.title()
        if any(phrase in title for phrase in ("Just a moment", "Sicherheitsprüfung", "403")):
            raise RuntimeError(
                f"hornbach: Cloudflare challenge page detected (title={title!r}). "
                "Playwright bypass failed."
            )

        body_text = page.inner_text("body")
        html = page.content()

    # --- Anti-silent-failure: confirm Hamburg market ---
    if _HH_MARKET_LABEL not in body_text:
        raise RuntimeError(
            f"hornbach: expected Hamburg market label '{_HH_MARKET_LABEL}' not found "
            "in rendered page — wrong market context or layout changed."
        )

    # --- Parse availability signals ---
    online_available, store_available = parse_availability_signals(body_text)

    # Anti-silent-failure: if NEITHER signal could be determined → health alert.
    if online_available is None and store_available is None:
        return None

    # Combine: available if either signal is positive.
    # Treat None as False for combination (conservative: unknown = not available).
    is_online = bool(online_available)
    is_store = bool(store_available)
    available = is_online or is_store
    pickup_only = is_store and not is_online

    # --- Extract price ---
    price = parse_price_from_html(html)

    suffix = " (Abholung Hamburg)" if pickup_only else ""
    return Offer(
        source=NAME,
        title=f"Midea PortaSplit — Hornbach{suffix}",
        url=URL,
        price=price,
        available=available,
        pickup_only=pickup_only,
        ean=EAN,
    )
