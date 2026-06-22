import os

import httpx

from .config import load_config
from .models import Offer
from .monitor import run_once
from .notify import send_telegram
from .sources import get_check, unknown_sources, KNOWN_SOURCES
from .state import load_state, save_state

CONFIG_PATH = "config.yaml"
STATE_PATH = "state.json"


def format_offer(offer: Offer) -> tuple[str, str]:
    pickup = " · 🏬 Abholung" if offer.pickup_only else ""
    price = f"{offer.price:.2f} €" if offer.price is not None else "Preis unbekannt"
    text = (
        "🟢 <b>Midea PortaSplit verfügbar!</b>\n"
        f"<b>{offer.source}</b> — <b>{price}</b>{pickup}\n"
        f"<i>{offer.title}</i>"
    )
    return text, offer.url


def cta_label(offer: Offer) -> str:
    return "🏬 Reservieren / Abholen" if offer.pickup_only else "🛒 Jetzt kaufen"


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    cfg = load_config(CONFIG_PATH)
    bad = unknown_sources(cfg.sources_enabled)
    if bad:
        raise ValueError(
            f"Unbekannte Quelle(n) in config.yaml sources_enabled: {bad}. "
            f"Bekannt: {sorted(KNOWN_SOURCES)}"
        )
    state = load_state(STATE_PATH)

    def notify_offer(offer: Offer) -> None:
        text, url = format_offer(offer)
        send_telegram(token, chat_id, text, button_text=cta_label(offer), button_url=url)

    def notify_health(name: str) -> None:
        send_telegram(
            token, chat_id,
            f"⚠️ Quelle <b>{name}</b> reagiert mehrfach nicht. Bitte Scraper prüfen.",
        )

    with httpx.Client() as client:
        state = run_once(cfg, state, get_check, notify_offer, notify_health, client)
    save_state(STATE_PATH, state)


if __name__ == "__main__":
    main()
