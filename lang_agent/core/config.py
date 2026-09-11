from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import os

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelSettings:
    provider: str
    name: str
    temperature: float


@dataclass(frozen=True)
class HealSettings:
    max_rounds: int


@dataclass(frozen=True)
class MemorySettings:
    enable_long_memory: bool
    chroma_dir: str


@dataclass(frozen=True)
class Settings:
    openapi_path: str
    base_url: str
    output_dir: str
    pytest_args: list[str]
    model: ModelSettings
    heal: HealSettings
    memory: MemorySettings


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def load_settings(config_path: str | Path, overrides: dict[str, Any] | None = None) -> Settings:
    load_dotenv(override=False)
    config_path = Path(config_path)
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if overrides:
        raw = _deep_merge(raw, overrides)

    model = raw.get("model", {}) or {}
    heal = raw.get("heal", {}) or {}
    memory = raw.get("memory", {}) or {}

    provider = str(model.get("provider", "openai"))
    model_name = str(model.get("name", os.getenv("OPENAI_MODEL", "gpt-4o-mini")))
    temperature = float(model.get("temperature", 0))

    return Settings(
        openapi_path=str(raw.get("openapi_path", "data/petstore.yaml")),
        base_url=str(raw.get("base_url", "http://localhost:8000")).rstrip("/"),
        output_dir=str(raw.get("output_dir", "generated_tests")),
        pytest_args=[str(x) for x in (raw.get("pytest_args", []) or [])],
        model=ModelSettings(provider=provider, name=model_name, temperature=temperature),
        heal=HealSettings(max_rounds=int(heal.get("max_rounds", 3))),
        memory=MemorySettings(
            enable_long_memory=bool(memory.get("enable_long_memory", False)),
            chroma_dir=str(memory.get("chroma_dir", ".chroma")),
        ),
    )
