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
from ..utils import LLMUnavailableError, RepairGateBlockedError, atomic_write_text
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


def _validate_repaired_code(original_code: str, repaired: str) -> None:
    original_asserts = original_code.count("assert ")
    repaired_asserts = repaired.count("assert ")
    if repaired_asserts < original_asserts and original_asserts > 0:
        raise RepairGateBlockedError(
            "修复方案存在断言削弱风险：断言数量下降，已拒绝写入长期记忆",
            user_hint="请人工检查修复结果是否保留了足够强的断言约束；若业务变更请更新测试数据而非直接删除断言。",
            details={
                "original_assert_count": original_asserts,
                "repaired_assert_count": repaired_asserts,
            },
        )
    if "def test_" not in repaired:
        raise RepairGateBlockedError(
            "修复后的文件中未找到任何 pytest 测试函数",
            user_hint="请确认生成结果为完整的 Python 文件，并保留 `def test_xxx(...)` 形式的测试函数。",
            details={},
        )
    try:
        compile(repaired, "<repaired-code>", "exec")
    except SyntaxError as exc:
        raise RepairGateBlockedError(
            f"修复后的代码存在语法错误：{exc.msg}",
            user_hint="请人工介入修复语法问题，或增加诊断置信度阈值避免低置信度自动修复。",
            details={"syntax_error": str(exc)},
        ) from exc


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
        raise LLMUnavailableError(
            "未配置可用的 LLM，无法执行自动修复",
            user_hint="请确认 `.env` 中已设置 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`，或暂时关闭需要 LLM 的自动修复功能仅做生成/执行。",
            details={"model_name": getattr(settings.model, "name", None)},
        )

    prompt = repair_prompt(
        original_code=original_code,
        error_log=error_log,
        error_type=error_type,
        error_summary=error_summary,
        few_shot_examples=few_shot_examples,
    )
    try:
        msg = llm.invoke(prompt)
    except Exception as exc:
        raise LLMUnavailableError(
            f"LLM 调用失败：{exc}",
            user_hint="请检查 LLM 服务可用性、网络代理与 API 配额；本次自愈已跳过，请人工介入。",
            details={"error_type": type(exc).__name__},
        ) from exc
    repaired = _extract_code(str(getattr(msg, "content", msg)))
    _validate_repaired_code(original_code, repaired)
    return repaired


def apply_repair_to_file(target: str | Path, repaired_code: str) -> Path:
    return atomic_write_text(target, repaired_code)
