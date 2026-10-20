from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..core.utils import atomic_write_text

DEFAULT_OUTPUT_ROOT = Path("output")
DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_ROOT / "latest_run_report.json"


def ensure_task_id(task_id: str | None = None) -> str:
    if task_id and task_id.strip():
        return task_id.strip()
    return uuid.uuid4().hex[:12]


def build_task_root(task_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return Path(output_root) / ensure_task_id(task_id)


def build_task_generated_dir(task_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return build_task_root(task_id, output_root) / "generated"


def build_task_reports_dir(task_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return build_task_root(task_id, output_root) / "reports"


def build_task_cache_dir(task_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return build_task_root(task_id, output_root) / "cache"


def build_task_report_path(task_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return build_task_reports_dir(task_id, output_root) / "run_report.json"


def build_task_cache_path(task_id: str, output_root: str | Path = DEFAULT_OUTPUT_ROOT) -> Path:
    return build_task_cache_dir(task_id, output_root) / "short_memory.json"


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
    task_id: str | None
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
    task_id: str | None
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
    payload = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    atomic_write_text(report_path, payload, encoding="utf-8")
    if report_path.resolve() != DEFAULT_REPORT_PATH.resolve():
        DEFAULT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(DEFAULT_REPORT_PATH, payload, encoding="utf-8")
    return report_path


def load_run_report(
    report_path: str | Path | None = None,
    *,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    if report_path is None and task_id:
        report_path = build_task_report_path(task_id)
    report_path = Path(report_path or DEFAULT_REPORT_PATH)
    if not report_path.exists():
        return None
    try:
        obj = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return obj
