from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    mode: str
    openapi_path: str
    output_dir: str
    tests_path: str
    endpoints: list[dict[str, Any]]
    scenarios: list[dict[str, Any]]
    generated_files: list[str]
    repair_round: int
    max_rounds: int
    failed_tests: list[dict[str, Any]]
    current_file: str
    current_error_log: str
    error_category: str
    error_type: str
    error_signature: str
    error_summary: str
    diagnosis_confidence: float
    diagnosis_reasons: list[str]
    diagnosis_actionable_hint: str
    short_memory_hit: bool
    retrieved_examples: list[str]
    proposed_fix_code: str
    final_result: dict[str, Any]
    handoff_report: dict[str, Any]
    repair_history: list[dict[str, Any]]
    last_exit_code: int
    last_stdout: str
    last_stderr: str
    tests_passed: bool
    long_memory_used: bool
    failures_count: int
    stopped_reason: str
