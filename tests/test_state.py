from src.state import is_new_alert, load_state, new_source_state, save_state


def test_load_missing_returns_empty(tmp_path):
    assert load_state(str(tmp_path / "nope.json")) == {"sources": {}}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    save_state(path, {"sources": {"obi": new_source_state()}})
    loaded = load_state(path)
    assert loaded["sources"]["obi"]["alerted"] is False


def test_is_new_alert_first_time():
    assert is_new_alert(None, 749.0) is True
    assert is_new_alert({"alerted": False, "alert_price": None}, 749.0) is True


def test_is_new_alert_suppresses_repeat_same_price():
    prev = {"alerted": True, "alert_price": 749.0}
    assert is_new_alert(prev, 749.0) is False


def test_is_new_alert_fires_on_price_drop():
    prev = {"alerted": True, "alert_price": 749.0}
    assert is_new_alert(prev, 699.0) is True


def test_load_corrupt_json_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json{")
    assert load_state(str(path)) == {"sources": {}}


def test_load_non_dict_json_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("[1, 2, 3]")
    assert load_state(str(path)) == {"sources": {}}


def test_load_valid_json_missing_sources_key_gets_injected(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"other": 1}')
    loaded = load_state(str(path))
    assert loaded["sources"] == {}
    assert loaded["other"] == 1
