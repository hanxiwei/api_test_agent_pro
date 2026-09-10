from __future__ import annotations

from .state import AgentState


def route_after_test_run(state: AgentState) -> str:
    failed = state.get("failed_tests") or []
    exit_code = int(state.get("last_exit_code", 1))
    if exit_code == 0 and not failed:
        return "passed"
    if failed:
        return "failed"
    return "errored"


def route_after_classification(state: AgentState) -> str:
    category = str(state.get("error_category") or "")
    confidence_raw = state.get("diagnosis_confidence")
    if category not in {"code_bug", "api_bug", "env_bug"}:
        return "unknown"
    if category != "code_bug":
        return category
    if confidence_raw is None:
        return category
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        return category
    if confidence < 0.7:
        return "handoff"
    return category


def route_after_short_memory(state: AgentState) -> str:
    return "hit" if bool(state.get("short_memory_hit")) else "miss"


def route_after_retest(state: AgentState) -> str:
    failed = state.get("failed_tests") or []
    exit_code = int(state.get("last_exit_code", 1))
    if exit_code == 0 and not failed:
        return "passed"

    rounds = int(state.get("repair_round", 0))
    max_rounds = int(state.get("max_rounds", 3))
    if rounds >= max_rounds:
        return "handoff"
    return "retry"

