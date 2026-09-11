from __future__ import annotations

import os
from typing import Any

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except Exception:  # type: ignore[no-redef]
    ChatOpenAI = None  # type: ignore[assignment]
    OpenAIEmbeddings = None  # type: ignore[assignment]

from ..core.config import ModelSettings


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _is_deepseek_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    return "deepseek.com" in base_url.lower()


def build_chat_llm(model: ModelSettings) -> ChatOpenAI | None:
    if ChatOpenAI is None:
        return None
    api_key = _env("OPENAI_API_KEY")
    if not api_key:
        return None

    kwargs: dict[str, Any] = {}
    base_url = _env("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    kwargs["timeout"] = float(_env("LLM_TIMEOUT_SECONDS") or "20")
    kwargs["max_retries"] = 1

    return ChatOpenAI(
        model=model.name,
        temperature=model.temperature,
        **kwargs,
    )


def build_embeddings() -> OpenAIEmbeddings | None:
    if OpenAIEmbeddings is None:
        return None
    api_key = _env("EMBEDDING_API_KEY") or _env("OPENAI_API_KEY")
    if not api_key:
        return None

    kwargs: dict[str, Any] = {}
    base_url = _env("EMBEDDING_BASE_URL") or _env("OPENAI_BASE_URL")
    model = _env("EMBEDDING_MODEL")

    # DeepSeek 当前在本项目中只承担 chat/completions；未单独配置 embedding 服务时，长期记忆自动降级为 no-op。
    if _is_deepseek_base_url(base_url) and not model and not _env("EMBEDDING_BASE_URL"):
        return None

    if base_url:
        kwargs["base_url"] = base_url
    if model:
        kwargs["model"] = model
    return OpenAIEmbeddings(**kwargs)
