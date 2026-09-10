from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pytest

from lang_agent.report import RunReport, load_run_report, save_run_report
from lang_agent.utils import (
    BaseSelfHealingError,
    OpenAPIParserError,
    atomic_write_text,
)


def test_atomic_write_text_overwrites_correctly(tmp_path: Path):
    target = tmp_path / "target.txt"
    target.write_text("original content", encoding="utf-8")
    new_text = "new content\n第二行"
    result = atomic_write_text(target, new_text)
    assert result == target
    assert target.read_text(encoding="utf-8") == new_text


def test_atomic_write_text_failure_preserves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "target.txt"
    original = "keep me safe\n"
    target.write_text(original, encoding="utf-8")

    original_fdopen = os.fdopen

    @contextmanager
    def fdopen_that_raises_on_write(fd, *args, **kwargs):
        f = original_fdopen(fd, *args, **kwargs)
        f_original_write = f.write

        def boom(text: str):
            raise OSError("disk full or whatever simulated")

        f.write = boom  # type: ignore[assignment]
        try:
            yield f
        finally:
            f_original_write("")  # no-op just to keep a ref
            f.close()

    monkeypatch.setattr(os, "fdopen", fdopen_that_raises_on_write)

    with pytest.raises(OSError):
        atomic_write_text(target, "broken content that must never land")

    # 原文件必须完整保留旧内容
    assert target.read_text(encoding="utf-8") == original
    # 临时文件也必须被清理（除了我们故意残留的 target.txt 不应再有 .target.txt.*.tmp）
    remaining_tmp = list(tmp_path.glob(".target.txt.*.tmp"))
    assert remaining_tmp == [], f"临时文件应该已清理, 但残留: {remaining_tmp}"


def test_atomic_write_text_handles_missing_parent(tmp_path: Path):
    target = tmp_path / "nested" / "deeper" / "file.txt"
    content = "deeply nested content"
    result = atomic_write_text(target, content)
    assert result == target
    assert target.read_text(encoding="utf-8") == content


def test_handoff_report_written_when_base_error_raised(tmp_path: Path):
    report_dir = tmp_path / "reports"
    report_path = report_dir / "run_report.json"
    err = OpenAPIParserError(
        "input openapi file not found",
        user_hint="请检查输入文件是否存在且为 OpenAPI 3.x 文档",
        details={"path": "/missing/petstore.yaml", "cause": "FileNotFoundError"},
    )

    handoff = {
        "category": "env_bug",
        "current_file": None,
        "reason": err.user_hint,
        "error_type": err.__class__.__name__,
        "error_signature": "",
        "error_log": str(err),
        "repair_round": 0,
        "details": err.details,
    }
    report = RunReport(
        mode="generate",
        ok=False,
        rounds=0,
        stopped_reason="stopped_on_env_bug",
        current_file=None,
        failures_count=0,
        short_memory_hit=False,
        long_memory_used=False,
        generated_files=[],
        repair_history=[],
        handoff_report=handoff,
        final_result={
            "last_exit_code": 1,
            "tests_passed": False,
            "error_type": handoff["error_type"],
            "error_message": str(err),
            "stdout_tail": "",
            "stderr_tail": handoff["reason"],
        },
    )
    saved = save_run_report(report, report_path)
    assert saved == report_path
    assert saved.exists()

    loaded = load_run_report(report_path)
    assert loaded is not None
    assert loaded["mode"] == "generate"
    assert loaded["ok"] is False
    assert loaded["stopped_reason"] == "stopped_on_env_bug"
    assert isinstance(loaded["handoff_report"], dict)
    assert loaded["handoff_report"]["category"] == "env_bug"
    assert loaded["handoff_report"]["error_type"] == "OpenAPIParserError"
    assert loaded["handoff_report"]["details"]["path"] == "/missing/petstore.yaml"
    assert loaded["final_result"]["stderr_tail"] == err.user_hint
    assert issubclass(type(err), BaseSelfHealingError)
