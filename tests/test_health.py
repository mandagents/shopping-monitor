from src.health import record_failure, record_success
from src.state import new_source_state


def test_warns_once_at_threshold():
    state = new_source_state()
    warns = []
    on_warn = lambda: warns.append(1)
    record_failure(state, 3, on_warn)
    record_failure(state, 3, on_warn)
    assert warns == []          # noch unter Schwelle
    record_failure(state, 3, on_warn)
    assert warns == [1]         # bei 3 genau einmal
    record_failure(state, 3, on_warn)
    assert warns == [1]         # kein erneuter Spam


def test_success_resets_counter_and_warned():
    state = new_source_state()
    on_warn = lambda: None
    record_failure(state, 1, on_warn)
    record_success(state)
    assert state["fail_count"] == 0
    assert state["warned"] is False
