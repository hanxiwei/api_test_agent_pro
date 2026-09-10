from __future__ import annotations

from pathlib import Path

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # type: ignore[no-redef]
    END = "__end__"  # type: ignore[assignment]
    START = "__start__"  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]

from ..config import Settings
from ..report import DEFAULT_REPORT_PATH, HealReport, RepairHistoryEntry, RunReport, save_run_report
from ..utils import BaseSelfHealingError
from .nodes import GraphNodes
from .router import (
    route_after_classification,
    route_after_retest,
    route_after_short_memory,
    route_after_test_run,
)
from .state import AgentState


def _build_handoff_from_exception(
    exc: BaseException,
    *,
    mode: str,
    current_file: str | None = None,
) -> dict:
    category = "env_bug"
    if exc.__class__.__name__ in {"DiagnosisBlockedError", "RepairGateBlockedError"}:
        category = "code_bug"
    elif exc.__class__.__name__ == "OpenAPIParserError":
        category = "env_bug"
    user_hint = getattr(exc, "user_hint", "")
    details = getattr(exc, "details", None) or {}
    reason = user_hint or str(exc)
    return {
        "category": category,
        "current_file": current_file,
        "reason": reason,
        "error_type": exc.__class__.__name__,
        "error_signature": "",
        "error_log": str(exc),
        "repair_round": 0,
        "details": details,
    }


def _compile_generate_graph(nodes: GraphNodes):
    if StateGraph is None:
        raise RuntimeError("langgraph 未安装，无法构建 generate 流程图")
    graph = StateGraph(AgentState)
    graph.add_node("parse_openapi_node", nodes.parse_openapi_node)
    graph.add_node("build_scenarios_node", nodes.build_scenarios_node)
    graph.add_node("generate_tests_node", nodes.generate_tests_node)
    graph.add_node("final_report_node", nodes.final_report_node)

    graph.add_edge(START, "parse_openapi_node")
    graph.add_edge("parse_openapi_node", "build_scenarios_node")
    graph.add_edge("build_scenarios_node", "generate_tests_node")
    graph.add_edge("generate_tests_node", "final_report_node")
    graph.add_edge("final_report_node", END)
    return graph.compile()


def _compile_heal_graph(nodes: GraphNodes):
    if StateGraph is None:
        raise RuntimeError("langgraph 未安装，无法构建 heal 流程图")
    graph = StateGraph(AgentState)
    graph.add_node("run_tests_node", nodes.run_tests_node)
    graph.add_node("collect_failures_node", nodes.collect_failures_node)
    graph.add_node("pick_failure_node", nodes.pick_failure_node)
    graph.add_node("classify_failure_node", nodes.classify_failure_node)
    graph.add_node("build_signature_node", nodes.build_signature_node)
    graph.add_node("lookup_short_memory_node", nodes.lookup_short_memory_node)
    graph.add_node("retrieve_long_memory_node", nodes.retrieve_long_memory_node)
    graph.add_node("repair_code_node", nodes.repair_code_node)
    graph.add_node("apply_fix_node", nodes.apply_fix_node)
    graph.add_node("retest_node", nodes.retest_node)
    graph.add_node("persist_memory_node", nodes.persist_memory_node)
    graph.add_node("build_handoff_report_node", nodes.build_handoff_report_node)
    graph.add_node("final_report_node", nodes.final_report_node)

    graph.add_edge(START, "run_tests_node")
    graph.add_edge("run_tests_node", "collect_failures_node")
    graph.add_conditional_edges(
        "collect_failures_node",
        route_after_test_run,
        {
            "passed": "final_report_node",
            "failed": "pick_failure_node",
            "errored": "final_report_node",
        },
    )
    graph.add_edge("pick_failure_node", "classify_failure_node")
    graph.add_conditional_edges(
        "classify_failure_node",
        route_after_classification,
        {
            "code_bug": "build_signature_node",
            "api_bug": "build_handoff_report_node",
            "env_bug": "build_handoff_report_node",
            "unknown": "build_handoff_report_node",
            "handoff": "build_handoff_report_node",
        },
    )
    graph.add_edge("build_signature_node", "lookup_short_memory_node")
    graph.add_conditional_edges(
        "lookup_short_memory_node",
        route_after_short_memory,
        {
            "hit": "apply_fix_node",
            "miss": "retrieve_long_memory_node",
        },
    )
    graph.add_edge("retrieve_long_memory_node", "repair_code_node")
    graph.add_edge("repair_code_node", "apply_fix_node")
    graph.add_edge("apply_fix_node", "retest_node")
    graph.add_conditional_edges(
        "retest_node",
        route_after_retest,
        {
            "passed": "persist_memory_node",
            "retry": "run_tests_node",
            "handoff": "build_handoff_report_node",
        },
    )
    graph.add_edge("persist_memory_node", "final_report_node")
    graph.add_edge("build_handoff_report_node", "final_report_node")
    graph.add_edge("final_report_node", END)
    return graph.compile()


def run_heal(
    *,
    settings: Settings,
    tests_path: str | Path,
    cache_path: str | Path = ".cache/short_memory.json",
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> HealReport:
    nodes = GraphNodes.build(settings=settings, cache_path=cache_path, report_path=report_path)
    graph = _compile_heal_graph(nodes)
    initial_state: AgentState = {
        "mode": "heal",
        "tests_path": str(Path(tests_path)),
        "repair_round": 0,
        "max_rounds": settings.heal.max_rounds,
        "repair_history": [],
        "generated_files": [],
        "stopped_reason": "",
        "short_memory_hit": False,
        "long_memory_used": False,
    }
    try:
        state = graph.invoke(initial_state)
    except BaseSelfHealingError as exc:
        handoff = _build_handoff_from_exception(exc, mode="heal", current_file=initial_state.get("current_file"))
        final_report = RunReport(
            mode="heal",
            ok=False,
            rounds=int(initial_state.get("repair_round", 0)),
            stopped_reason=f"stopped_on_{handoff['category']}",
            current_file=handoff.get("current_file"),
            failures_count=0,
            short_memory_hit=bool(initial_state.get("short_memory_hit", False)),
            long_memory_used=bool(initial_state.get("long_memory_used", False)),
            generated_files=[str(x) for x in (initial_state.get("generated_files") or [])],
            repair_history=[dict(x) for x in (initial_state.get("repair_history") or [])],
            handoff_report=handoff,
            final_result={
                "last_exit_code": 1,
                "tests_passed": False,
                "error_type": handoff.get("error_type"),
                "error_message": str(exc),
                "stdout_tail": "",
                "stderr_tail": handoff.get("reason", ""),
            },
        )
        save_run_report(final_report, report_path)
        return HealReport(
            ok=False,
            rounds=int(initial_state.get("repair_round", 0)),
            stopped_reason=f"stopped_on_{handoff['category']}",
            current_file=handoff.get("current_file"),
            failures_count=0,
            short_memory_hit=bool(initial_state.get("short_memory_hit", False)),
            long_memory_used=bool(initial_state.get("long_memory_used", False)),
            repair_history=[dict(x) for x in (initial_state.get("repair_history") or [])],
            handoff_report=handoff,
            report_path=str(report_path),
        )

    final_result = dict(state.get("final_result") or {})
    stopped_reason = str(final_result.get("stopped_reason") or "")
    if not stopped_reason:
        if state.get("handoff_report"):
            stopped_reason = f"stopped_on_{state.get('handoff_report', {}).get('category', 'handoff')}"
        elif bool(state.get("tests_passed")):
            stopped_reason = "healed" if int(state.get("repair_round", 0)) > 0 else "all_passed"
        else:
            stopped_reason = "finished"
    return HealReport(
        ok=bool(final_result.get("ok", state.get("tests_passed", False))),
        rounds=int(state.get("repair_round", 0)),
        stopped_reason=stopped_reason,
        current_file=state.get("current_file"),
        failures_count=int(final_result.get("failures_count", len(state.get("failed_tests") or []))),
        short_memory_hit=bool(state.get("short_memory_hit", False)),
        long_memory_used=bool(state.get("long_memory_used", False)),
        repair_history=[dict(x) for x in (state.get("repair_history") or [])],
        handoff_report=state.get("handoff_report"),
        report_path=str(state.get("report_path") or report_path),
    )


def run_generate(
    *,
    settings: Settings,
    openapi_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> list[Path]:
    nodes = GraphNodes.build(settings=settings, cache_path=".cache/short_memory.json", report_path=report_path)
    graph = _compile_generate_graph(nodes)
    initial_state: AgentState = {
        "mode": "generate",
        "openapi_path": str(Path(openapi_path)),
        "output_dir": str(Path(output_dir)),
        "repair_round": 0,
        "generated_files": [],
        "failed_tests": [],
        "repair_history": [],
        "tests_passed": True,
        "last_exit_code": 0,
        "stopped_reason": "generated",
    }
    try:
        state = graph.invoke(initial_state)
    except BaseSelfHealingError as exc:
        handoff = _build_handoff_from_exception(exc, mode="generate")
        final_report = RunReport(
            mode="generate",
            ok=False,
            rounds=0,
            stopped_reason=f"stopped_on_{handoff['category']}",
            current_file=None,
            failures_count=0,
            short_memory_hit=False,
            long_memory_used=False,
            generated_files=[],
            repair_history=[RepairHistoryEntry(
                round=0,
                file="",
                error_category=handoff.get("category", "env_bug"),
                error_type=handoff.get("error_type", exc.__class__.__name__),
                error_signature="",
                short_memory_hit=False,
                long_memory_used=False,
                outcome="blocked",
                notes=str(handoff.get("reason", str(exc))),
            ).to_dict()],
            handoff_report=handoff,
            final_result={
                "last_exit_code": 1,
                "tests_passed": False,
                "error_type": handoff.get("error_type"),
                "error_message": str(exc),
                "stdout_tail": "",
                "stderr_tail": handoff.get("reason", ""),
            },
        )
        save_run_report(final_report, report_path)
        raise
    return [Path(x) for x in (state.get("generated_files") or [])]
