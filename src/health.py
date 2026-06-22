def record_failure(src_state: dict, threshold: int, on_warn) -> None:
    src_state["fail_count"] = src_state.get("fail_count", 0) + 1
    if src_state["fail_count"] >= threshold and not src_state.get("warned"):
        on_warn()
        src_state["warned"] = True


def record_success(src_state: dict) -> None:
    src_state["fail_count"] = 0
    src_state["warned"] = False
