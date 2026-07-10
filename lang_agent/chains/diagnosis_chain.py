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


def _heuristic_category(error_type: str, error_log: str) -> str:
    t = error_type.lower()
    log = error_log.lower()
    if any(x in t for x in ["connectionerror", "timeout", "proxyerror", "ssLError".lower()]):
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
    )


def diagnose(settings: Settings, error_log: str) -> Diagnosis:
    llm = build_chat_llm(settings.model)
    if llm is not None:
        try:
            d = _llm_diagnose(settings, error_log)
            if d.error_category and d.error_signature:
                return d
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
    )
