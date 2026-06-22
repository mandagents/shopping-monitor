import pytest

from src.notify import send_telegram


class _FakeResp:
    def raise_for_status(self):
        return None


class _FakeClient:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResp()


def test_send_telegram_builds_payload_with_button():
    client = _FakeClient()
    send_telegram(
        "TOKEN", "123", "Verfügbar!",
        button_text="Zum Shop", button_url="https://shop.example/p",
        client=client,
    )
    call = client.calls[0]
    assert "botTOKEN/sendMessage" in call["url"]
    assert call["json"]["chat_id"] == "123"
    assert call["json"]["text"] == "Verfügbar!"
    kb = call["json"]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["url"] == "https://shop.example/p"
    assert kb[0][0]["text"] == "Zum Shop"
    assert call["json"]["parse_mode"] == "HTML"
    assert call["json"]["disable_web_page_preview"] is False


def test_send_telegram_without_button_has_no_markup():
    client = _FakeClient()
    send_telegram("TOKEN", "123", "Health-Warnung", client=client)
    assert "reply_markup" not in client.calls[0]["json"]


class _ErrResp:
    def raise_for_status(self):
        raise RuntimeError("HTTP 500")


class _ErrClient:
    def post(self, url, json, timeout):
        return _ErrResp()


def test_send_telegram_propagates_http_error():
    with pytest.raises(RuntimeError):
        send_telegram("TOKEN", "123", "x", client=_ErrClient())
