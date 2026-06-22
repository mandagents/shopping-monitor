import json
import os


def new_source_state() -> dict:
    return {"alerted": False, "alert_price": None, "fail_count": 0, "warned": False}


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"sources": {}}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return {"sources": {}}
    if not isinstance(data, dict):
        return {"sources": {}}
    if "sources" not in data:
        data["sources"] = {}
    return data


def save_state(path: str, state: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def is_new_alert(prev: dict | None, price: float) -> bool:
    if prev is None or not prev.get("alerted"):
        return True
    prev_price = prev.get("alert_price")
    return prev_price is None or price < prev_price
