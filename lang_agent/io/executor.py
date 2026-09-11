from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.utils import TestRunnerError


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


def _user_hint_for(test_path: Path, exit_code: int, stderr: str) -> str:
    log = stderr.lower()
    if exit_code == 5:
        return "pytest 未收集到任何用例，请确认 tests 目录是否为生成后的分层工程，且 testpaths=testcases 已生效。"
    if "modulenotfounderror" in log or "importerror" in log:
        return "执行 pytest 时出现导入错误，请确认 generated_tests 目录下有 api/utils/conftest.py/pytest.ini，并从项目根运行。"
    if "file not found" in log:
        return "tests_path 指向的目录不存在，请确认 `python cli.py generate` 已先完成生成。"
    return (
        f"pytest 执行失败（exit_code={exit_code}）。请先手动运行 `python -m pytest {test_path} -q` 复现问题，再回到自愈流程。"
    )


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

    exit_code = int(p.returncode)
    stdout = p.stdout or ""
    stderr = p.stderr or ""
    if exit_code not in {0, 1} and not report and not failures:
        raise TestRunnerError(
            f"pytest 进程异常退出（exit_code={exit_code}）",
            user_hint=_user_hint_for(test_path, exit_code, stderr),
            details={
                "command": cmd,
                "exit_code": exit_code,
                "stdout_tail": stdout[-1000:],
                "stderr_tail": stderr[-1000:],
            },
        )
    return PytestRunResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        report=report,
        failures=failures,
    )
