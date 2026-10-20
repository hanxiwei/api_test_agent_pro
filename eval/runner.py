from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from lang_agent.core.config import load_settings
from lang_agent.graph.runner import run_generate, run_heal
from lang_agent.llm.factory import build_chat_llm
from lang_agent.memory.short_memory import ShortMemory

MOCK_PORT = 8000

# 生成工程必须包含的关键文件（黄金集结构判定）
REQUIRED_FILES = [
    "conftest.py",
    "pytest.ini",
    "api/__init__.py",
    "utils/__init__.py",
    "config/settings.yaml",
]


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _start_mock() -> subprocess.Popen:
    """启动本地 mock 服务，返回进程句柄；若端口已被占用则返回 None 表示复用外部服务。"""
    if _port_in_use(MOCK_PORT):
        return None  # 已有服务在跑，复用即可
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "mock_api_server.py")],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if _port_in_use(MOCK_PORT):
            return proc
        time.sleep(0.1)
    proc.terminate()
    raise RuntimeError("mock server 启动超时，请检查端口 8000 是否可用")


def _stop_mock(proc: subprocess.Popen | None) -> None:
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def _load_cases(cases_path: Path) -> dict:
    data = yaml.safe_load(cases_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"评测集格式错误：{cases_path}")
    return data


def _check_llm(settings) -> bool:
    return build_chat_llm(settings.model) is not None


def _run_case_once(case: dict, settings, golden_dir: Path, runs_dir: Path, trial: int) -> dict:
    """复制基准工程 -> 覆盖坏文件 -> 跑 run_heal -> 判分。"""
    name = case["name"]
    workdir = runs_dir / name / f"trial_{trial}"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(golden_dir, workdir)

    patch = PROJECT_ROOT / case["patch"]
    target = workdir / "testcases" / patch.name
    shutil.copy(patch, target)

    original_asserts = target.read_text(encoding="utf-8").count("assert ")

    task_id = f"eval_{name}_{trial}"
    report = run_heal(settings=settings, tests_path=str(workdir), task_id=task_id)

    fixed_asserts = target.read_text(encoding="utf-8").count("assert ")
    tests_passed = bool(report.ok)
    assert_ok = fixed_asserts >= original_asserts

    expect_pass = bool(case.get("expect_pass", True))
    expect_category = case.get("expect_category")
    handoff_category = (report.handoff_report or {}).get("category")
    if expect_pass:
        passed = tests_passed and assert_ok
    else:
        passed = not tests_passed
        if expect_category and handoff_category != expect_category:
            passed = False

    return {
        "trial": trial,
        "tests_passed": tests_passed,
        "assert_not_weakened": assert_ok,
        "stopped_reason": report.stopped_reason,
        "rounds": report.rounds,
        "handoff_category": handoff_category,
        "passed": passed,
        "workdir": str(workdir),
    }


def _check_structure(output_dir: Path) -> tuple[bool, list[str]]:
    """校验生成工程的关键结构，返回 (是否完整, 缺失项列表)。"""
    missing = [p for p in REQUIRED_FILES if not (output_dir / p).exists()]
    has_test = bool(list((output_dir / "testcases").glob("test_*.py")))
    if not has_test:
        missing.append("testcases/test_*.py")
    return (not missing), missing


def _check_collect(output_dir: Path) -> bool:
    """用 pytest --collect-only 验证工程能否被正常收集。"""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(output_dir), "--collect-only", "-q"],
        capture_output=True,
        text=True,
        timeout=90,
    )
    return proc.returncode == 0


def _run_generate_case_once(case: dict, settings, runs_dir: Path, trial: int) -> dict:
    """跑 run_generate，校验结构完整 + 可 collect。"""
    name = case["name"]
    output_dir = runs_dir / name / f"gen_trial_{trial}"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    openapi_path = PROJECT_ROOT / case["openapi_path"]
    task_id = f"eval_{name}_{trial}"

    generated = run_generate(
        settings=settings,
        openapi_path=openapi_path,
        output_dir=output_dir,
        task_id=task_id,
    )

    structure_ok, missing = _check_structure(output_dir)
    collect_ok = _check_collect(output_dir)
    passed = structure_ok and collect_ok

    return {
        "trial": trial,
        "generated_files": len(generated),
        "structure_ok": structure_ok,
        "missing": missing,
        "collect_ok": collect_ok,
        "passed": passed,
        "workdir": str(output_dir),
    }


def _setup_memory_workdir(case: dict, golden_dir: Path, runs_dir: Path, trial: int) -> tuple[Path, Path]:
    """复制基准工程 + 覆盖坏文件，返回 (workdir, target)。"""
    name = case["name"]
    workdir = runs_dir / name / f"trial_{trial}"
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(golden_dir, workdir)
    patch = PROJECT_ROOT / case["patch"]
    target = workdir / "testcases" / patch.name
    shutil.copy(patch, target)
    return workdir, target


def _run_short_memory_reuse_case(case: dict, settings, golden_dir: Path, runs_dir: Path, trial: int) -> dict:
    """短期记忆复用：同一个 bug 修两次，第二次应命中短期记忆、零 LLM 复用修复结果。"""
    name = case["name"]
    workdir, target = _setup_memory_workdir(case, golden_dir, runs_dir, trial)
    cache_path = runs_dir / name / f"trial_{trial}" / "short_memory.json"
    report_dir = runs_dir / name / f"trial_{trial}" / "reports"

    # 第一次：未命中，走 LLM 修复并写入短期记忆
    first = run_heal(
        settings=settings,
        tests_path=str(workdir),
        task_id=f"eval_{name}_{trial}_first",
        cache_path=cache_path,
        report_path=report_dir / "first.json",
    )

    # 重新埋回 bug，模拟相同错误再次出现
    shutil.copy(PROJECT_ROOT / case["patch"], target)

    # 第二次：应命中短期记忆，直接复用修复结果（不再调 LLM）
    second = run_heal(
        settings=settings,
        tests_path=str(workdir),
        task_id=f"eval_{name}_{trial}_second",
        cache_path=cache_path,
        report_path=report_dir / "second.json",
    )

    passed = bool(first.ok and (not first.short_memory_hit) and second.short_memory_hit and second.ok)
    return {
        "trial": trial,
        "first_ok": bool(first.ok),
        "first_hit": bool(first.short_memory_hit),
        "second_ok": bool(second.ok),
        "second_hit": bool(second.short_memory_hit),
        "passed": passed,
        "workdir": str(workdir),
    }


def _run_no_pollution_case(case: dict, settings, golden_dir: Path, runs_dir: Path, trial: int) -> dict:
    """防污染：后端缺陷被 handoff，未通过 pytest 的修复不应写入记忆。"""
    name = case["name"]
    workdir, _ = _setup_memory_workdir(case, golden_dir, runs_dir, trial)
    cache_path = runs_dir / name / f"trial_{trial}" / "short_memory.json"
    report_dir = runs_dir / name / f"trial_{trial}" / "reports"

    report = run_heal(
        settings=settings,
        tests_path=str(workdir),
        task_id=f"eval_{name}_{trial}",
        cache_path=cache_path,
        report_path=report_dir / "run.json",
    )

    memory = ShortMemory.load(cache_path)
    memory_empty = len(memory.cache) == 0
    handoff_category = (report.handoff_report or {}).get("category")
    expect_category = case.get("expect_category")
    category_ok = (expect_category is None) or (handoff_category == expect_category)

    passed = bool((not report.ok) and memory_empty and category_ok)
    return {
        "trial": trial,
        "tests_passed": bool(report.ok),
        "memory_empty": memory_empty,
        "handoff_category": handoff_category,
        "passed": passed,
        "workdir": str(workdir),
    }


def _evaluate_case(case: dict, settings, golden_dir: Path, runs_dir: Path, pass_k: int) -> dict:
    trials = []
    kind = case.get("kind", "heal")
    for trial in range(pass_k):
        try:
            if case.get("mode") == "generate":
                trials.append(_run_generate_case_once(case, settings, runs_dir, trial))
            elif kind == "short_memory_reuse":
                trials.append(_run_short_memory_reuse_case(case, settings, golden_dir, runs_dir, trial))
            elif kind == "no_pollution":
                trials.append(_run_no_pollution_case(case, settings, golden_dir, runs_dir, trial))
            else:
                trials.append(_run_case_once(case, settings, golden_dir, runs_dir, trial))
        except Exception as exc:  # noqa: BLE001 - 评测需捕获所有异常并记录
            trials.append({"trial": trial, "passed": False, "error": f"{type(exc).__name__}: {exc}"})
    passed_trials = sum(1 for t in trials if t.get("passed"))
    return {
        "name": case["name"],
        "suite": case.get("suite", ""),
        "mode": case.get("mode", "heal"),
        "kind": kind,
        "pass_k": pass_k,
        "passed_trials": passed_trials,
        "pass_rate": passed_trials / pass_k if pass_k else 0.0,
        "trials": trials,
    }


def _print_summary(results: list[dict]) -> None:
    print("\n================ Agent 评测结果 ================")
    for r in results:
        rate = r["pass_rate"]
        mark = "PASS" if rate >= 1.0 else ("PARTIAL" if rate > 0 else "FAIL")
        print(f"[{mark}] {r['name']:<22} suite={r['suite']:<11} Pass@{r['pass_k']}={rate:.2f}")
        for t in r["trials"]:
            if t.get("error"):
                extra = t["error"]
            elif r.get("mode") == "generate":
                extra = f"structure={t.get('structure_ok')} collect={t.get('collect_ok')} missing={t.get('missing')}"
            elif r.get("kind") == "short_memory_reuse":
                extra = f"first(ok={t.get('first_ok')},hit={t.get('first_hit')}) second(ok={t.get('second_ok')},hit={t.get('second_hit')})"
            elif r.get("kind") == "no_pollution":
                extra = f"passed={t.get('tests_passed')} memory_empty={t.get('memory_empty')} handoff={t.get('handoff_category')}"
            else:
                extra = f"passed={t.get('tests_passed')} assert_ok={t.get('assert_not_weakened')} reason={t.get('stopped_reason')} handoff={t.get('handoff_category')}"
            print(f"      trial {t['trial']}: {'OK' if t.get('passed') else 'NG'}  {extra}")
    total = len(results)
    passed = sum(1 for r in results if r["pass_rate"] >= 1.0)
    print("----------------------------------------------")
    print(f"case 通过率（Pass@k=1.0）：{passed}/{total}")


def _write_markdown_report(results: list[dict], path: Path) -> None:
    """生成一份人可读的 Markdown 评测报告表。"""
    from datetime import datetime

    total = len(results)
    passed = sum(1 for r in results if r["pass_rate"] >= 1.0)
    lines: list[str] = [
        "# Agent 评测报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总览：**{total}** 个 case，**{passed}** 个通过，通过率 **{passed / total * 100:.0f}%**（Pass@k=1.0 口径）",
        "",
        "## 汇总",
        "",
        "| case | suite | mode | Pass@k | 结果 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        rate = r["pass_rate"]
        mark = "PASS" if rate >= 1.0 else ("PARTIAL" if rate > 0 else "FAIL")
        lines.append(f"| {r['name']} | {r['suite']} | {r['mode']} | {rate:.2f} | {mark} |")

    lines += ["", "## 明细", ""]
    for r in results:
        rate = r["pass_rate"]
        mark = "PASS" if rate >= 1.0 else ("PARTIAL" if rate > 0 else "FAIL")
        lines.append(f"### {r['name']}  ——  {mark}（Pass@{r['pass_k']}={rate:.2f}）")
        lines.append("")
        lines.append("| trial | 关键指标 |")
        lines.append("| --- | --- |")
        for t in r["trials"]:
            if t.get("error"):
                detail = f"异常：{t['error']}"
            elif r.get("mode") == "generate":
                detail = f"结构完整={t.get('structure_ok')}，collect={t.get('collect_ok')}，缺失={t.get('missing') or '无'}"
            elif r.get("kind") == "short_memory_reuse":
                detail = (
                    f"第一次(修好={t.get('first_ok')},命中={t.get('first_hit')})，"
                    f"第二次(修好={t.get('second_ok')},命中={t.get('second_hit')})"
                )
            elif r.get("kind") == "no_pollution":
                detail = f"pytest 变绿={t.get('tests_passed')}，记忆为空={t.get('memory_empty')}，handoff={t.get('handoff_category')}"
            else:
                detail = (
                    f"pytest 变绿={t.get('tests_passed')}，断言不削弱={t.get('assert_not_weakened')}，"
                    f"停止原因={t.get('stopped_reason')}，handoff 分类={t.get('handoff_category')}"
                )
            lines.append(f"| {t['trial']} | {detail} |")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="API Test Agent 回测评测脚本")
    parser.add_argument("--cases", default="eval/cases.yaml", help="评测集定义文件")
    parser.add_argument("--suite", default=None, help="只跑指定 suite（repair/gate/generation/memory）")
    parser.add_argument("--case", default=None, help="只跑指定 case 名")
    parser.add_argument("--pass-k", type=int, default=None, help="每个 case 重复次数，覆盖 yaml")
    parser.add_argument("--golden", default=None, help="基准工程目录，覆盖 yaml")
    parser.add_argument("--config", default="config.yaml", help="项目 config.yaml")
    parser.add_argument("--with-mock", dest="with_mock", action="store_true", default=True, help="自动启动 mock 服务（默认）")
    parser.add_argument("--no-mock", dest="with_mock", action="store_false", help="不启动 mock 服务")
    parser.add_argument("--dry-run", action="store_true", help="只加载与校验，不真正执行")
    parser.add_argument("--out", default="eval/runs/summary.json", help="汇总结果输出路径（JSON）")
    parser.add_argument("--report", default="eval/runs/report.md", help="人读评测报告输出路径（Markdown）")
    args = parser.parse_args()

    cases_path = PROJECT_ROOT / args.cases
    cases_data = _load_cases(cases_path)
    golden_dir = PROJECT_ROOT / (args.golden or cases_data.get("golden_dir", "generated_tests"))
    pass_k = args.pass_k or int(cases_data.get("pass_k", 1))
    cases = cases_data["cases"]
    if args.suite:
        cases = [c for c in cases if c.get("suite") == args.suite]
    if args.case:
        cases = [c for c in cases if c.get("name") == args.case]
    if not cases:
        raise SystemExit("没有匹配的 case，请检查 --suite/--case 参数")

    # 前置校验
    if not golden_dir.exists():
        raise SystemExit(f"基准工程不存在：{golden_dir}，请先 `python cli.py generate -i data/petstore.yaml -o generated_tests`")
    for case in cases:
        if case.get("mode") == "generate":
            openapi = PROJECT_ROOT / case.get("openapi_path", "")
            if not openapi.exists():
                raise SystemExit(f"OpenAPI 文档不存在：{openapi}")
        else:
            patch = PROJECT_ROOT / case.get("patch", "")
            if not patch.exists():
                raise SystemExit(f"评测坏文件不存在：{patch}")

    settings = load_settings(PROJECT_ROOT / args.config)

    if args.dry_run:
        print(f"[dry-run] 已加载 {len(cases)} 个 case，基准工程={golden_dir}，pass_k={pass_k}")
        for case in cases:
            print(f"  - {case['name']} (suite={case.get('suite')}, expect_pass={case.get('expect_pass')})")
        return

    llm_available = _check_llm(settings)
    if not llm_available:
        print("[warn] 未检测到可用的 LLM（OPENAI_API_KEY 未配置），自愈类 case 会走启发式兜底并大概率 handoff。")

    mock_proc = None
    if args.with_mock:
        mock_proc = _start_mock()
        print(f"[info] mock 服务就绪（端口 {MOCK_PORT}）")

    runs_dir = PROJECT_ROOT / "eval" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    results = []
    try:
        for case in cases:
            print(f"[run] {case['name']} ...")
            results.append(_evaluate_case(case, settings, golden_dir, runs_dir, pass_k))
    finally:
        if mock_proc is not None:
            _stop_mock(mock_proc)

    _print_summary(results)

    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"cases": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = PROJECT_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown_report(results, report_path)

    print(f"\n汇总已写入：{out_path}")
    print(f"人读报告已写入：{report_path}")


if __name__ == "__main__":
    main()
