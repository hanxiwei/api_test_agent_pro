from pathlib import Path

from lang_agent.report import RunReport, load_run_report, save_run_report


def test_save_and_load_run_report(tmp_path: Path):
    report_path = tmp_path / "latest_run_report.json"
    report = RunReport(
        mode="heal",
        ok=True,
        rounds=1,
        stopped_reason="healed",
        current_file="generated_tests/test_demo.py",
        failures_count=0,
        short_memory_hit=False,
        long_memory_used=True,
        generated_files=["generated_tests/test_demo.py"],
        repair_history=[{"round": 1, "outcome": "passed"}],
        handoff_report=None,
        final_result={"last_exit_code": 0, "tests_passed": True},
    )
    save_run_report(report, report_path)
    loaded = load_run_report(report_path)
    assert loaded is not None
    assert loaded["mode"] == "heal"
    assert loaded["ok"] is True
    assert loaded["repair_history"][0]["outcome"] == "passed"

