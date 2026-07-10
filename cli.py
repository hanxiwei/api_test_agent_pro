from __future__ import annotations

import json
from pathlib import Path

import click

from lang_agent.config import load_settings
from lang_agent.graph.runner import run_generate, run_heal
from lang_agent.report import load_run_report


@click.group()
@click.option("--config", "config_path", default="config.yaml", show_default=True, type=click.Path())
@click.pass_context
def cli(ctx: click.Context, config_path: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option("-i", "--input", "openapi_path", required=True, type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", default="generated_tests", show_default=True, type=click.Path())
@click.option("--base-url", default=None)
@click.option("--model-name", default=None)
@click.pass_context
def generate(
    ctx: click.Context,
    openapi_path: str,
    output_dir: str,
    base_url: str | None,
    model_name: str | None,
) -> None:
    overrides = {}
    if base_url:
        overrides["base_url"] = base_url
    if model_name:
        overrides.setdefault("model", {})["name"] = model_name
    settings = load_settings(ctx.obj["config_path"], overrides=overrides)
    files = run_generate(settings=settings, openapi_path=openapi_path, output_dir=output_dir)
    click.echo(json.dumps({"generated": [str(x) for x in files]}, ensure_ascii=False, indent=2))


@cli.command()
@click.option("-i", "--input", "openapi_path", type=click.Path(exists=True))
@click.option("-t", "--tests", "tests_path", type=click.Path(exists=True))
@click.option("-o", "--output", "output_dir", default="generated_tests", show_default=True, type=click.Path())
@click.option("-r", "--rounds", "max_rounds", default=None, type=int)
@click.option("--base-url", default=None)
@click.option("--model-name", default=None)
@click.option("--enable-long-memory/--disable-long-memory", default=None)
@click.pass_context
def heal(
    ctx: click.Context,
    openapi_path: str | None,
    tests_path: str | None,
    output_dir: str,
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
    settings = load_settings(ctx.obj["config_path"], overrides=overrides)

    final_tests_path = tests_path
    if openapi_path:
        run_generate(settings=settings, openapi_path=openapi_path, output_dir=output_dir)
        final_tests_path = output_dir

    if not final_tests_path:
        raise click.UsageError("未能确定 tests 目录。")

    report = run_heal(settings=settings, tests_path=Path(final_tests_path))
    click.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


@cli.command()
def report() -> None:
    latest = load_run_report()
    if latest is None:
        click.echo(json.dumps({"message": "暂无最近一次运行报告"}, ensure_ascii=False, indent=2))
        return
    click.echo(json.dumps(latest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
