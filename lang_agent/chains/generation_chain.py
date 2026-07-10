from __future__ import annotations

from pathlib import Path

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except Exception:  # type: ignore[no-redef]
    def retry(*args, **kwargs):  # type: ignore[no-redef]
        def deco(fn):
            return fn

        return deco

    def stop_after_attempt(*args, **kwargs):  # type: ignore[no-redef]
        return None

    def wait_exponential(*args, **kwargs):  # type: ignore[no-redef]
        return None

from ..config import Settings
from ..scenario_builder import Scenario
from .llm_factory import build_chat_llm
from .prompts import generation_prompt


def _extract_code(text: str) -> str:
    if "```" not in text:
        return text.strip() + "\n"
    parts = text.split("```")
    for i in range(len(parts) - 1):
        block = parts[i + 1]
        if block.lstrip().startswith("python"):
            block = block.lstrip()[6:]
        code = block.strip("\n")
        if code:
            return code.strip() + "\n"
    return text.strip() + "\n"


def _placeholder_path(path: str) -> str:
    out = path
    while "{" in out and "}" in out:
        start = out.index("{")
        end = out.index("}", start)
        key = out[start + 1 : end]
        out = out[:start] + f"{{{key}}}" + out[end + 1 :]
        break
    return out


def _template_test_code(base_url: str, scenario: Scenario) -> str:
    lines: list[str] = []
    lines.append("import os")
    lines.append("import uuid")
    lines.append("")
    lines.append("import pytest")
    lines.append("import requests")
    lines.append("")
    lines.append(f'BASE_URL = os.getenv("API_BASE_URL", {base_url!r}).rstrip("/")')
    lines.append("")
    lines.append("")
    lines.append("def _format_path(path: str, **params: str) -> str:")
    lines.append("    for k, v in params.items():")
    lines.append('        path = path.replace("{" + k + "}", str(v))')
    lines.append("    return path")
    lines.append("")
    lines.append("")
    for ep in scenario.endpoints:
        test_name = f"test_{scenario.name}_{ep.operation_id}".lower()
        lines.append(f"def {test_name}():")
        path = _placeholder_path(ep.path)
        if "{" in path and "}" in path:
            param_name = path[path.index("{") + 1 : path.index("}")]
            lines.append(f'    url = BASE_URL + _format_path("{path}", {param_name}="1")')
        else:
            lines.append(f'    url = BASE_URL + "{path}"')

        if ep.method in {"post", "put", "patch"}:
            lines.append('    payload = {"name": "test-" + uuid.uuid4().hex[:8]}')
            lines.append(f'    r = requests.{ep.method}(url, json=payload, timeout=10)')
        else:
            lines.append(f'    r = requests.{ep.method}(url, timeout=10)')
        lines.append("    assert r.status_code < 500")
        lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _llm_generate(settings: Settings, scenario: Scenario) -> str:
    llm = build_chat_llm(settings.model)
    if llm is None:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法使用 LLM 生成")
    prompt = generation_prompt(settings.base_url, scenario)
    msg = llm.invoke(prompt)
    return _extract_code(str(getattr(msg, "content", msg)))


def generate_pytest_file(settings: Settings, scenario: Scenario, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"test_{scenario.name}.py"

    code: str
    llm = build_chat_llm(settings.model)
    if llm is None:
        code = _template_test_code(settings.base_url, scenario)
    else:
        try:
            code = _llm_generate(settings, scenario)
        except Exception:
            code = _template_test_code(settings.base_url, scenario)

    file_path.write_text(code, encoding="utf-8")
    return file_path
