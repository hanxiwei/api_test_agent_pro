from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TestFailure:
    nodeid: str
    file: str
    call_longrepr: str


@dataclass(frozen=True)
class PytestRunResult:
    exit_code: int
    stdout: str
    stderr: str
    report: dict[str, Any] | None
    failures: list[TestFailure]


def run_pytest(test_path: str | Path, pytest_args: list[str], report_path: str | Path) -> PytestRunResult:
    test_path = Path(test_path)
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "--json-report",
        f"--json-report-file={report_path}",
        *pytest_args,
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    report = None
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            report = None

    failures: list[TestFailure] = []
    if report and isinstance(report.get("tests"), list):
        for t in report["tests"]:
            if not isinstance(t, dict):
                continue
            if t.get("outcome") != "failed":
                continue
            nodeid = str(t.get("nodeid", ""))
            file_part = nodeid.split("::", 1)[0] if nodeid else ""
            call = t.get("call") or {}
            longrepr = ""
            if isinstance(call, dict):
                longrepr = str(call.get("longrepr", "")) or str(call.get("crash", "")) or ""
            failures.append(TestFailure(nodeid=nodeid, file=file_part, call_longrepr=longrepr))

    return PytestRunResult(
        exit_code=int(p.returncode),
        stdout=p.stdout or "",
        stderr=p.stderr or "",
        report=report,
        failures=failures,
    )
