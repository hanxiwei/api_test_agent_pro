from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_REPORT_PATH = Path(".cache/latest_run_report.json")


@dataclass(frozen=True)
class RepairHistoryEntry:
    round: int
    file: str
    error_category: str
    error_type: str
    error_signature: str
    short_memory_hit: bool
    long_memory_used: bool
    outcome: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunReport:
    mode: str
    ok: bool
    rounds: int
    stopped_reason: str
    current_file: str | None
    failures_count: int
    short_memory_hit: bool
    long_memory_used: bool
    generated_files: list[str]
    repair_history: list[dict[str, Any]]
    handoff_report: dict[str, Any] | None
    final_result: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HealReport:
    ok: bool
    rounds: int
    stopped_reason: str
    current_file: str | None
    failures_count: int
    short_memory_hit: bool
    long_memory_used: bool
    repair_history: list[dict[str, Any]] | None = None
    handoff_report: dict[str, Any] | None = None
    report_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def save_run_report(report: RunReport, report_path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def load_run_report(report_path: str | Path = DEFAULT_REPORT_PATH) -> dict[str, Any] | None:
    report_path = Path(report_path)
    if not report_path.exists():
        return None
    try:
        obj = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return obj
