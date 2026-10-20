from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import click

from lang_agent.core.config import load_settings
from lang_agent.graph.runner import run_generate, run_heal
from lang_agent.io.report import (
    build_task_generated_dir,
    build_task_report_path,
    ensure_task_id,
    load_run_report,
)


@click.group()
@click.option("--config", "config_path", default="config.yaml", show_default=True, type=click.Path())
@click.pass_context
def cli(ctx: click.Context, config_path: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


def _run_with_workers(workers: int, fn, /, *args, **kwargs):
    if workers <= 1:
        return fn(*args, **kwargs)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future = executor.submit(fn, *args, **kwargs)
        return future.result()


def _validate_sandbox_kind(value: str) -> str:
    normalized = (value or "host").strip().lower()
    if normalized not in {"host", "docker"}:
        raise click.BadParameter("sandbox 仅支持 host 或 docker")
    return normalized


@cli.command()
@click.option("-i", "--input", "openapi_path", required=True, type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", default=None, type=click.Path())
@click.option("--task-id", default=None)
@click.option("--workers", default=1, show_default=True, type=int)
@click.option("--sandbox", "sandbox_kind", default="host", show_default=True)
@click.option("--base-url", default=None)
@click.option("--model-name", default=None)
@click.pass_context
def generate(
    ctx: click.Context,
    openapi_path: str,
    output_dir: str | None,
    task_id: str | None,
    workers: int,
    sandbox_kind: str,
    base_url: str | None,
    model_name: str | None,
) -> None:
    overrides = {}
    if base_url:
        overrides["base_url"] = base_url
    if model_name:
        overrides.setdefault("model", {})["name"] = model_name
    sandbox_kind = _validate_sandbox_kind(sandbox_kind)
    settings = load_settings(ctx.obj["config_path"], overrides=overrides)
    task_id = ensure_task_id(task_id)
    resolved_output_dir = Path(output_dir) if output_dir else build_task_generated_dir(task_id)
    report_path = build_task_report_path(task_id)
    files = _run_with_workers(
        workers,
        run_generate,
        settings=settings,
        openapi_path=openapi_path,
        output_dir=resolved_output_dir,
        task_id=task_id,
        report_path=report_path,
        sandbox_kind=sandbox_kind,
    )
    click.echo(
        json.dumps(
            {
                "task_id": task_id,
                "output_dir": str(resolved_output_dir),
                "report_path": str(report_path),
                "sandbox": sandbox_kind,
                "generated": [str(x) for x in files],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@cli.command()
@click.option("-i", "--input", "openapi_path", type=click.Path(exists=True))
@click.option("-t", "--tests", "tests_path", type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", default=None, type=click.Path())
@click.option("--task-id", default=None)
@click.option("--workers", default=1, show_default=True, type=int)
@click.option("--sandbox", "sandbox_kind", default="host", show_default=True)
@click.option("-r", "--rounds", "max_rounds", default=None, type=int)
@click.option("--base-url", default=None)
@click.option("--model-name", default=None)
@click.option("--enable-long-memory/--disable-long-memory", default=None)
@click.pass_context
def heal(
    ctx: click.Context,
    openapi_path: str | None,
    tests_path: str | None,
    output_dir: str | None,
    task_id: str | None,
    workers: int,
    sandbox_kind: str,
    max_rounds: int | None,
    base_url: str | None,
    model_name: str | None,
    enable_long_memory: bool | None,
) -> None:
    if not openapi_path and not tests_path:
        raise click.UsageError("`heal` 至少需要传入 `-i/--input` 或 `-t/--tests` 其中之一。")
    overrides = {}
    if enable_long_memory is not None:
        overrides.setdefault("memory", {})["enable_long_memory"] = enable_long_memory
    if max_rounds is not None:
        overrides.setdefault("heal", {})["max_rounds"] = max_rounds
    if base_url:
        overrides["base_url"] = base_url
    if model_name:
        overrides.setdefault("model", {})["name"] = model_name
    sandbox_kind = _validate_sandbox_kind(sandbox_kind)
    settings = load_settings(ctx.obj["config_path"], overrides=overrides)
    task_id = ensure_task_id(task_id)
    resolved_output_dir = Path(output_dir) if output_dir else build_task_generated_dir(task_id)
    report_path = build_task_report_path(task_id)

    final_tests_path = tests_path
    if openapi_path:
        _run_with_workers(
            workers,
            run_generate,
            settings=settings,
            openapi_path=openapi_path,
            output_dir=resolved_output_dir,
            task_id=task_id,
            report_path=report_path,
            sandbox_kind=sandbox_kind,
        )
        final_tests_path = str(resolved_output_dir)

    if not final_tests_path:
        raise click.UsageError("未能确定 tests 目录。")

    report = _run_with_workers(
        workers,
        run_heal,
        settings=settings,
        tests_path=Path(final_tests_path),
        task_id=task_id,
        report_path=report_path,
        sandbox_kind=sandbox_kind,
    )
    click.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


@cli.command()
@click.option("--task-id", default=None)
def report(task_id: str | None) -> None:
    latest = load_run_report(task_id=task_id)
    if latest is None:
        click.echo(json.dumps({"message": "暂无最近一次运行报告"}, ensure_ascii=False, indent=2))
        return
    click.echo(json.dumps(latest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
