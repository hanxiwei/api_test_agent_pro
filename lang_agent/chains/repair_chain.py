from __future__ import annotations

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
from .llm_factory import build_chat_llm
from .prompts import repair_prompt


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


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def repair_test_file(
    settings: Settings,
    original_code: str,
    error_log: str,
    error_type: str,
    error_summary: str,
    few_shot_examples: list[str],
) -> str:
    llm = build_chat_llm(settings.model)
    if llm is None:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法使用 LLM 修复")

    prompt = repair_prompt(
        original_code=original_code,
        error_log=error_log,
        error_type=error_type,
        error_summary=error_summary,
        few_shot_examples=few_shot_examples,
    )
    msg = llm.invoke(prompt)
    return _extract_code(str(getattr(msg, "content", msg)))
