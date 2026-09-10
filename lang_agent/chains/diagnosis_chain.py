from __future__ import annotations

import json
import re
from dataclasses import dataclass

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
from ..signatures import extract_error_signature, extract_error_type
from .llm_factory import build_chat_llm
from .prompts import diagnosis_prompt


@dataclass(frozen=True)
class Diagnosis:
    error_category: str
    error_type: str
    error_signature: str
    error_summary: str
    confidence: float = 0.0
    reasons: tuple[str, ...] = ()
    actionable_hint: str = ""


def _safe_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


def _safe_reasons(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _heuristic_reasons(category: str, error_type: str, error_log: str) -> tuple[str, ...]:
    reasons: list[str] = []
    log = error_log.lower()
    t = error_type.lower()
    if category == "env_bug":
        reasons.append("错误类型或日志包含连接异常、超时或域名解析失败特征")
        if any(x in t for x in ["connectionerror", "timeout", "proxyerror", "sslerror"]):
            reasons.append(f"错误类型命中环境问题：{error_type}")
        if any(x in log for x in ["connection refused", "name or service not known", "timed out"]):
            reasons.append("错误日志包含 localhost:8000 未启动或网络异常关键词")
    elif category == "code_bug":
        reasons.append("错误类型或日志包含语法、导入、名称、类型等代码层错误特征")
        if any(x in t for x in ["syntaxerror", "importerror", "modulenotfounderror", "nameerror", "typeerror"]):
            reasons.append(f"错误类型命中代码问题：{error_type}")
    else:
        reasons.append("错误类型或日志包含断言失败、响应异常或 JSON 解析失败等接口表现特征")
        if "assert" in t or "assertionerror" in t:
            reasons.append(f"错误类型命中断言/接口表现问题：{error_type}")
    if not reasons:
        reasons.append("基于启发式规则默认分类")
    return tuple(reasons[:4])


def _heuristic_hint(category: str, error_type: str, error_log: str) -> str:
    log = error_log.lower()
    t = error_type.lower()
    if category == "env_bug" or any(x in t for x in ["connectionerror", "timeout"]) or "connection refused" in log:
        return "请先启动测试目标服务，例如 `python mock_api_server.py`，或在 config/sidebar 中把 base_url 指向可访问环境，并检查本地网络与代理。"
    if category == "code_bug":
        return "请检查测试文件的语法、导入路径、fixture 名称是否正确，或进入自愈流程仅修改测试代码本身。"
    if category == "api_bug" or "assert" in t:
        return "请对比接口文档与真实响应，核对断言状态码、字段名与路径参数；若后端已变更，应更新测试数据而非放宽断言。"
    return "请核对失败日志中的断言与堆栈，并确认测试目标环境与数据是否符合预期。"


def _heuristic_category(error_type: str, error_log: str) -> str:
    t = error_type.lower()
    log = error_log.lower()
    if any(x in t for x in ["connectionerror", "timeout", "proxyerror", "sslerror"]):
        return "env_bug"
    if any(x in log for x in ["connection refused", "name or service not known", "timed out"]):
        return "env_bug"
    if any(x in t for x in ["syntaxerror", "importerror", "modulenotfounderror", "nameerror", "typeerror"]):
        return "code_bug"
    if "assert" in t or "assertionerror" in t:
        return "api_bug"
    if any(x in log for x in ["status_code", "response", "jsondecodeerror", "httperror"]):
        return "api_bug"
    return "code_bug"


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def _llm_diagnose(settings: Settings, error_log: str) -> Diagnosis:
    llm = build_chat_llm(settings.model)
    if llm is None:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法使用 LLM 诊断")
    prompt = diagnosis_prompt(error_log)
    msg = llm.invoke(prompt)
    text = str(getattr(msg, "content", msg)).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    obj = json.loads(text)
    return Diagnosis(
        error_category=str(obj.get("error_category", "")),
        error_type=str(obj.get("error_type", "")),
        error_signature=str(obj.get("error_signature", "")),
        error_summary=str(obj.get("error_summary", "")),
        confidence=_safe_float(obj.get("confidence", 0.0)),
        reasons=_safe_reasons(obj.get("reasons", [])),
        actionable_hint=str(obj.get("actionable_hint", "")).strip(),
    )


def diagnose(settings: Settings, error_log: str) -> Diagnosis:
    llm = build_chat_llm(settings.model)
    if llm is not None:
        try:
            d = _llm_diagnose(settings, error_log)
            if d.error_category and d.error_signature:
                reasons = d.reasons or _heuristic_reasons(d.error_category, d.error_type, error_log)
                hint = d.actionable_hint or _heuristic_hint(d.error_category, d.error_type, error_log)
                confidence = d.confidence or 0.6
                return Diagnosis(
                    error_category=d.error_category,
                    error_type=d.error_type,
                    error_signature=d.error_signature,
                    error_summary=d.error_summary,
                    confidence=confidence,
                    reasons=reasons,
                    actionable_hint=hint,
                )
        except Exception:
            pass

    error_type = extract_error_type(error_log)
    signature = extract_error_signature(error_log)
    category = _heuristic_category(error_type, error_log)
    summary = f"{error_type}: {signature}" if signature else error_type
    return Diagnosis(
        error_category=category,
        error_type=error_type,
        error_signature=signature,
        error_summary=summary,
        confidence=0.55,
        reasons=_heuristic_reasons(category, error_type, error_log),
        actionable_hint=_heuristic_hint(category, error_type, error_log),
    )
