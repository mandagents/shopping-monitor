"""AliExpress availability check via headless Playwright (de-DE locale).

AliExpress is a client-side-rendered SPA.  Raw httpx sees a near-empty shell;
all product data loads via JS.  This source uses Playwright to render the page
fully and then extracts availability and price from AliExpress's embedded JS
data blob (``window.runParams`` / ``__INIT_DATA__`` / ``__AER_DATA__``).

Detection logic
---------------
1. Render the item URL with a de-DE locale context.
2. If a bot-challenge / slider / "punish" page is detected → return None
   (→ health-check alert).  Never silently guess.
3. If the unavailable marker is present ("nicht verfügbar an ihrem standort" /
   "not available") → return Offer(..., available=False).
4. If the marker is absent → try to extract the real product price from the
   embedded JS blobs.  If no real price can be extracted → return None
   (→ health-check), never alert with a guessed price.

Anti-silent-failure guards
--------------------------
- Bot-challenge detected  → None  (health, not crash)
- Unavailable marker      → Offer(available=False)  (clean "monitored, not here")
- Marker absent + no real price extracted  → None  (health, not alert)
- Exception in Playwright propagates upward → monitor marks source as failed

Signature follows the uniform ``check(client) -> Offer | None`` interface;
``client`` (httpx.Client) is intentionally ignored.
"""
from __future__ import annotations

import json
import re

from ..models import Offer
from .playwright_base import playwright_page

NAME = "aliexpress"
ITEM_ID = "1005012500647890"
URL = f"https://de.aliexpress.com/item/{ITEM_ID}.html"
EAN = "4048164116478"

# The reliable "item not available in your region" markers AliExpress renders.
# Lowercase comparisons are used — case insensitive.
_UNAVAILABLE_MARKERS = [
    "nicht verfügbar an ihrem standort",
    "leider ist dieser artikel an ihrem standort derzeit nicht verfügbar",
    "not available in your location",
    "this item is currently not available",
    "item is not available",
]

# Bot-challenge / punish-page URL fragments and page-text markers.
_CHALLENGE_URL_FRAGMENTS = [
    "_____tmd_____",
    "punish",
    "captcha",
    "sec-captcha",
    "challenge",
]
_CHALLENGE_TEXT_MARKERS = [
    "please slide to verify",
    "bitte schieben sie",
    "security verification",
    "robot check",
    "human verification",
]

# Regex to match a plausible EUR price like "569,00" or "569.00"
# Only used when the numeric value is already isolated from the data blob.
_EUR_PRICE_RE = re.compile(r"^(\d{2,4})[.,](\d{2})$")


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-testable, no browser)
# ---------------------------------------------------------------------------


def is_bot_challenge(url: str, page_text: str) -> bool:
    """Return True if the page looks like a bot-challenge / punish page.

    Args:
        url: the final URL after navigation (post-redirect).
        page_text: lowercased visible text of the page body.

    Returns:
        True when a known challenge signal is found.
    """
    url_lower = url.lower()
    for fragment in _CHALLENGE_URL_FRAGMENTS:
        if fragment in url_lower:
            return True
    for marker in _CHALLENGE_TEXT_MARKERS:
        if marker in page_text:
            return True
    return False


def is_unavailable(page_text: str) -> bool:
    """Return True if the page text contains an 'unavailable in your region' marker.

    Args:
        page_text: lowercased visible text of the page body.

    Returns:
        True when any known unavailability string is found.
    """
    for marker in _UNAVAILABLE_MARKERS:
        if marker in page_text:
            return True
    return False


def extract_price_from_run_params(run_params: dict) -> float | None:
    """Try to extract a real EUR product price from a ``runParams``-style dict.

    AliExpress embeds ``window.runParams = { data: { priceModule: {...}, ... } }``
    in a ``<script>`` tag.  We look for:
    - ``data.priceModule.minAmount.value``  (numeric)
    - ``data.priceModule.maxAmount.value``
    - ``data.priceModule.minActivityAmount.value``
    - ``data.priceModule.formatedActivityPrice``  (formatted string like "€ 569,00")
    - ``data.priceModule.formatedPrice``

    Args:
        run_params: the parsed ``runParams`` / ``data`` dict.

    Returns:
        A float EUR price, or None if none can be reliably extracted.
    """
    # Navigate to the data sub-dict if the caller passed the full runParams
    data = run_params.get("data", run_params)

    price_module = data.get("priceModule") if isinstance(data, dict) else None
    if not isinstance(price_module, dict):
        return None

    # Prefer numeric fields (most reliable — no currency symbols to strip)
    for key in (
        "minActivityAmount",
        "minAmount",
        "maxActivityAmount",
        "maxAmount",
    ):
        entry = price_module.get(key)
        if isinstance(entry, dict):
            value = entry.get("value")
            if value is not None:
                try:
                    price = float(value)
                    if price > 0:
                        return price
                except (ValueError, TypeError):
                    pass
        elif entry is not None:
            try:
                price = float(entry)
                if price > 0:
                    return price
            except (ValueError, TypeError):
                pass

    # Fallback: formatted price strings like "€ 569,00" or "569.00 €"
    for key in ("formatedActivityPrice", "formatedPrice"):
        raw = price_module.get(key)
        if not isinstance(raw, str):
            continue
        # Strip currency symbol and whitespace, normalise decimal separator
        cleaned = raw.replace("€", "").replace("$", "").replace("US", "").strip()
        cleaned = cleaned.replace(",", ".")
        # Remove any thousand-separator dots that appear before the last dot
        # e.g. "1.234.56" → keep only last segment: simple heuristic
        parts = cleaned.split(".")
        if len(parts) == 3:
            # likely "1.234.56" format — join first two as thousands
            cleaned = parts[0] + parts[1] + "." + parts[2]
        try:
            price = float(cleaned)
            if price > 0:
                return price
        except (ValueError, TypeError):
            pass

    return None


def parse_embedded_data(html: str) -> float | None:
    """Scan the rendered HTML for AliExpress embedded JS data blobs and extract price.

    Tries several known embedding patterns:
    1. ``window.runParams = {...}``  (classic, still common)
    2. ``__INIT_DATA__ = {...}``
    3. ``__AER_DATA__ = {...}``
    4. ``<script type="application/json" data-role="...">`` blocks

    Args:
        html: the full rendered HTML string.

    Returns:
        A float EUR price, or None if no reliable price can be extracted.
    """
    # Pattern 1: window.runParams = { ... }; or window.runParams={...}
    for pattern in (
        r"window\.runParams\s*=\s*(\{.*?\});\s*(?:window\.|</script>|$)",
        r"window\.runParams\s*=\s*(\{.+?\})\s*;",
    ):
        for m in re.finditer(pattern, html, re.DOTALL):
            candidate = m.group(1)
            # Trim to balanced braces to avoid grabbing too much
            candidate = _trim_to_balanced(candidate)
            if candidate is None:
                continue
            try:
                obj = json.loads(candidate)
                price = extract_price_from_run_params(obj)
                if price is not None:
                    return price
            except (json.JSONDecodeError, ValueError):
                pass

    # Pattern 2: __INIT_DATA__ or __AER_DATA__ assignments
    for var_name in ("__INIT_DATA__", "__AER_DATA__", "window._dida_config_"):
        pattern = rf"{re.escape(var_name)}\s*=\s*(\{{.+?\}})\s*;"
        for m in re.finditer(pattern, html, re.DOTALL):
            candidate = _trim_to_balanced(m.group(1))
            if candidate is None:
                continue
            try:
                obj = json.loads(candidate)
                price = extract_price_from_run_params(obj)
                if price is not None:
                    return price
            except (json.JSONDecodeError, ValueError):
                pass

    # Pattern 3: Look for priceModule JSON directly as a heuristic
    # Matches  "priceModule":{"minAmount":{"value":569.0,...},...}
    pm_pattern = re.compile(r'"priceModule"\s*:\s*(\{)', re.DOTALL)
    for m in pm_pattern.finditer(html):
        start = m.start(1)
        candidate = _trim_to_balanced(html[start:])
        if candidate is None:
            continue
        try:
            pm = json.loads(candidate)
            price = extract_price_from_run_params({"priceModule": pm})
            if price is not None:
                return price
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _trim_to_balanced(text: str) -> str | None:
    """Return the shortest prefix of *text* that forms a balanced JSON object.

    Args:
        text: a string starting with ``{``.

    Returns:
        The balanced substring, or ``None`` if the input is not balanced within
        the first 500 000 characters (safety limit).
    """
    if not text or text[0] != "{":
        return None
    depth = 0
    in_string = False
    escape_next = False
    limit = min(len(text), 500_000)
    for i, ch in enumerate(text[:limit]):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[: i + 1]
    return None


# ---------------------------------------------------------------------------
# Main check() function
# ---------------------------------------------------------------------------


def check(client) -> Offer | None:  # noqa: ANN001  (client is httpx.Client, ignored)
    """Check AliExpress item availability using Playwright.

    Renders the item page in a de-DE locale browser context, then applies the
    following decision tree:

    - Bot-challenge detected → None  (health-check, not crash)
    - Unavailable marker present → Offer(available=False)
    - Marker absent + real price extracted → Offer(available=True, price=<float>)
    - Marker absent + price extraction fails → None  (health-check)

    Args:
        client: httpx.Client — not used (Playwright handles all I/O).

    Returns:
        An :class:`~src.models.Offer` or None on failure / challenge.
    """
    with playwright_page(timeout_ms=45_000) as page:
        # Signal de-DE locale so AliExpress serves German-language content and
        # EUR pricing.  Must be set before the first navigation.
        page.set_extra_http_headers({"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
        page.goto(URL, wait_until="networkidle")

        final_url = page.url
        page_text = page.inner_text("body").lower()
        html = page.content()

    # --- Step 2: bot-challenge check ---
    if is_bot_challenge(final_url, page_text):
        # Do NOT crash; return None so the health-check counter increments.
        return None

    # --- Step 3: unavailability check ---
    if is_unavailable(page_text):
        return Offer(
            source=NAME,
            title="Midea PortaSplit — AliExpress (Versand DE)",
            url=URL,
            price=None,
            available=False,
            pickup_only=False,
            ean=EAN,
        )

    # --- Step 4: item appears available — must extract a real product price ---
    price = parse_embedded_data(html)

    if price is None:
        # Marker absent but price extraction failed — anti-silent-failure guard.
        # Return None so the health-check counter increments rather than
        # sending a false-positive alert with an unknown price.
        return None

    return Offer(
        source=NAME,
        title="Midea PortaSplit — AliExpress (Versand DE)",
        url=URL,
        price=price,
        available=True,
        pickup_only=False,
        ean=EAN,
    )
