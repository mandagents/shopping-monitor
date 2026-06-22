import httpx

_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(token, chat_id, text, *, button_text=None, button_url=None, client=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": button_text or "Zum Shop", "url": button_url}]]
        }
    c = client or httpx
    resp = c.post(_API.format(token=token), json=payload, timeout=15)
    resp.raise_for_status()
    return resp
