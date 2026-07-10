from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..chains.diagnosis_chain import diagnose
from ..chains.generation_chain import generate_pytest_file
from ..chains.repair_chain import repair_test_file
from ..config import Settings
from ..executor import run_pytest
from ..memory.long_memory import LongMemory
from ..memory.retriever import retrieve_few_shot_examples
from ..memory.short_memory import ShortMemory
from ..parser import parse_openapi
from ..report import RepairHistoryEntry, RunReport, save_run_report
from ..scenario_builder import build_scenarios
from .state import AgentState


def _failure_log_for_file(state: AgentState, file_rel: str) -> str:
    failures = state.get("failed_tests") or []
    chunks: list[str] = []
    for item in failures:
        if str(item.get("file", "")) == file_rel:
            chunks.append(f"nodeid={item.get('nodeid', '')}\n{item.get('call_longrepr', '')}".strip())
    return "\n\n".join(x for x in chunks if x).strip()


def _resolve_test_file(tests_path: str | Path, current_file: str) -> Path:
    tests_path = Path(tests_path)
    current_path = Path(current_file)
    candidates = [
        current_path,
        tests_path / current_path,
        tests_path / current_path.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@dataclass
class GraphNodes:
    settings: Settings
    cache_path: Path
    report_path: Path
    short_memory: ShortMemory
    long_memory: LongMemory | None

    @classmethod
    def build(
        cls,
        *,
        settings: Settings,
        cache_path: str | Path,
        report_path: str | Path,
    ) -> "GraphNodes":
        cache_path = Path(cache_path)
        short_memory = ShortMemory.load(cache_path)
        long_memory = (
            LongMemory(chroma_dir=settings.memory.chroma_dir) if settings.memory.enable_long_memory else None
        )
        return cls(
            settings=settings,
            cache_path=cache_path,
            report_path=Path(report_path),
            short_memory=short_memory,
            long_memory=long_memory,
        )

    def parse_openapi_node(self, state: AgentState) -> AgentState:
        endpoints = parse_openapi(state["openapi_path"])
        data: list[dict[str, Any]] = []
        for ep in endpoints:
            data.append(
                {
                    "method": ep.method,
                    "path": ep.path,
                    "operation_id": ep.operation_id,
                    "tags": ep.tags,
                    "parameters": ep.parameters,
                    "request_schema": ep.request_schema,
                    "responses": ep.responses,
                }
            )
        return {"endpoints": data}

    def build_scenarios_node(self, state: AgentState) -> AgentState:
        endpoints = parse_openapi(state["openapi_path"])
        scenarios = build_scenarios(endpoints)
        data: list[dict[str, Any]] = []
        for s in scenarios:
            data.append({"resource": s.resource, "name": s.name})
        return {"scenarios": data}

    def generate_tests_node(self, state: AgentState) -> AgentState:
        endpoints = parse_openapi(state["openapi_path"])
        scenarios = build_scenarios(endpoints)
        output_dir = Path(state["output_dir"])
        generated = [str(generate_pytest_file(self.settings, s, output_dir)) for s in scenarios]
        return {
            "generated_files": generated,
            "tests_path": str(output_dir),
        }

    def run_tests_node(self, state: AgentState) -> AgentState:
        report_path = Path(".cache") / "pytest_report.json"
        result = run_pytest(state["tests_path"], self.settings.pytest_args, report_path)
        failed_tests = [
            {"nodeid": f.nodeid, "file": f.file, "call_longrepr": f.call_longrepr}
            for f in result.failures
        ]
        return {
            "failed_tests": failed_tests,
            "last_exit_code": result.exit_code,
            "last_stdout": result.stdout,
            "last_stderr": result.stderr,
            "tests_passed": result.exit_code == 0 and not failed_tests,
        }

    def collect_failures_node(self, state: AgentState) -> AgentState:
        failures = state.get("failed_tests") or []
        if failures:
            return {"failures_count": len(failures)}
        return {"failures_count": 0}

    def pick_failure_node(self, state: AgentState) -> AgentState:
        failures = state.get("failed_tests") or []
        if not failures:
            return {}
        current_file = str(failures[0].get("file", ""))
        return {
            "current_file": current_file,
            "current_error_log": _failure_log_for_file(state, current_file),
        }

    def classify_failure_node(self, state: AgentState) -> AgentState:
        current_error_log = str(state.get("current_error_log") or "")
        d = diagnose(self.settings, current_error_log)
        return {
            "error_category": d.error_category,
            "error_type": d.error_type,
            "error_signature": d.error_signature,
            "error_summary": d.error_summary,
        }

    def build_signature_node(self, state: AgentState) -> AgentState:
        return {
            "error_signature": str(state.get("error_signature") or ""),
            "error_type": str(state.get("error_type") or ""),
            "error_summary": str(state.get("error_summary") or ""),
        }

    def lookup_short_memory_node(self, state: AgentState) -> AgentState:
        current_file = str(state.get("current_file") or "")
        error_signature = str(state.get("error_signature") or "")
        cache_key = f"{current_file}::{error_signature}"
        cached = self.short_memory.get(cache_key)
        if cached:
            return {
                "short_memory_hit": True,
                "proposed_fix_code": cached,
            }
        return {"short_memory_hit": False}

    def retrieve_long_memory_node(self, state: AgentState) -> AgentState:
        error_type = str(state.get("error_type") or "")
        error_signature = str(state.get("error_signature") or "")
        few_shots = retrieve_few_shot_examples(
            self.long_memory,
            error_type=error_type,
            error_signature=error_signature,
            k=3,
        )
        return {
            "retrieved_examples": few_shots,
            "long_memory_used": bool(few_shots),
        }

    def repair_code_node(self, state: AgentState) -> AgentState:
        file_path = _resolve_test_file(state["tests_path"], state["current_file"])
        original_code = file_path.read_text(encoding="utf-8")
        fixed_code = repair_test_file(
            self.settings,
            original_code=original_code,
            error_log=str(state.get("current_error_log") or ""),
            error_type=str(state.get("error_type") or ""),
            error_summary=str(state.get("error_summary") or ""),
            few_shot_examples=[str(x) for x in (state.get("retrieved_examples") or [])],
        )
        return {"proposed_fix_code": fixed_code}

    def apply_fix_node(self, state: AgentState) -> AgentState:
        file_path = _resolve_test_file(state["tests_path"], state["current_file"])
        proposed_fix_code = str(state.get("proposed_fix_code") or "")
        file_path.write_text(proposed_fix_code, encoding="utf-8")

        repair_round = int(state.get("repair_round", 0)) + 1
        history = list(state.get("repair_history") or [])
        history.append(
            RepairHistoryEntry(
                round=repair_round,
                file=str(state.get("current_file") or ""),
                error_category=str(state.get("error_category") or ""),
                error_type=str(state.get("error_type") or ""),
                error_signature=str(state.get("error_signature") or ""),
                short_memory_hit=bool(state.get("short_memory_hit")),
                long_memory_used=bool(state.get("long_memory_used")),
                outcome="fix_applied",
                notes="已回写 current_file，等待全量回归验证",
            ).to_dict()
        )
        return {"repair_round": repair_round, "repair_history": history}

    def retest_node(self, state: AgentState) -> AgentState:
        report_path = Path(".cache") / "pytest_report_after_fix.json"
        result = run_pytest(state["tests_path"], self.settings.pytest_args, report_path)
        failed_tests = [
            {"nodeid": f.nodeid, "file": f.file, "call_longrepr": f.call_longrepr}
            for f in result.failures
        ]
        history = list(state.get("repair_history") or [])
        if history:
            last = dict(history[-1])
            last["outcome"] = "passed" if result.exit_code == 0 and not failed_tests else "failed"
            last["notes"] = "全量回归通过" if result.exit_code == 0 and not failed_tests else "全量回归仍失败"
            history[-1] = last
        return {
            "failed_tests": failed_tests,
            "last_exit_code": result.exit_code,
            "last_stdout": result.stdout,
            "last_stderr": result.stderr,
            "tests_passed": result.exit_code == 0 and not failed_tests,
            "repair_history": history,
        }

    def persist_memory_node(self, state: AgentState) -> AgentState:
        current_file = str(state.get("current_file") or "")
        cache_key = f"{current_file}::{state.get('error_signature', '')}"
        fixed_code = str(state.get("proposed_fix_code") or "")
        if fixed_code:
            self.short_memory.set(cache_key, fixed_code)
            if self.long_memory is not None and not bool(state.get("short_memory_hit")):
                self.long_memory.add_validated_fix(
                    error_type=str(state.get("error_type") or ""),
                    error_signature=str(state.get("error_signature") or ""),
                    error_log=str(state.get("current_error_log") or ""),
                    fixed_code=fixed_code,
                    test_file=current_file,
                    repair_round=int(state.get("repair_round", 0)),
                )
        self.short_memory.dump(self.cache_path)
        return {}

    def build_handoff_report_node(self, state: AgentState) -> AgentState:
        category = str(state.get("error_category") or "unknown")
        reason = str(state.get("error_summary") or state.get("stopped_reason") or "")
        if category not in {"api_bug", "env_bug"}:
            category = "code_bug"
            reason = reason or "达到最大修复轮次，需人工介入"
        return {
            "handoff_report": {
                "category": category,
                "current_file": state.get("current_file"),
                "reason": reason,
                "error_type": state.get("error_type"),
                "error_signature": state.get("error_signature"),
                "error_log": state.get("current_error_log"),
                "repair_round": state.get("repair_round", 0),
            }
        }

    def final_report_node(self, state: AgentState) -> AgentState:
        failed_tests = state.get("failed_tests") or []
        ok = bool(state.get("tests_passed", False))
        stopped_reason = str(state.get("stopped_reason") or "")
        if not stopped_reason:
            handoff = state.get("handoff_report") or {}
            handoff_category = str(handoff.get("category") or "")
            if handoff_category:
                stopped_reason = f"stopped_on_{handoff_category}"
            elif ok:
                stopped_reason = "healed" if int(state.get("repair_round", 0)) > 0 else "all_passed"
            elif int(state.get("last_exit_code", 0)) != 0 and not failed_tests:
                stopped_reason = "pytest_failed_without_reported_failures"
            else:
                stopped_reason = "finished"
        report = RunReport(
            mode=str(state.get("mode") or ""),
            ok=ok,
            rounds=int(state.get("repair_round", 0)),
            stopped_reason=stopped_reason,
            current_file=state.get("current_file"),
            failures_count=len(failed_tests),
            short_memory_hit=bool(state.get("short_memory_hit", False)),
            long_memory_used=bool(state.get("long_memory_used", False)),
            generated_files=[str(x) for x in (state.get("generated_files") or [])],
            repair_history=[dict(x) for x in (state.get("repair_history") or [])],
            handoff_report=state.get("handoff_report"),
            final_result={
                "last_exit_code": int(state.get("last_exit_code", 0)),
                "tests_passed": ok,
                "stdout_tail": str(state.get("last_stdout") or "")[-1000:],
                "stderr_tail": str(state.get("last_stderr") or "")[-1000:],
            },
        )
        report_file = save_run_report(report, self.report_path)
        self.short_memory.dump(self.cache_path)
        return {
            "final_result": report.to_dict(),
            "report_path": str(report_file),
            "stopped_reason": stopped_reason,
        }
