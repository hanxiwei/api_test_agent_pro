from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ShortMemory:
    cache: dict[str, str]

    @classmethod
    def empty(cls) -> "ShortMemory":
        return cls(cache={})

    def get(self, key: str) -> str | None:
        return self.cache.get(key)

    def set(self, key: str, fixed_code: str) -> None:
        self.cache[key] = fixed_code

    def dump(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ShortMemory":
        path = Path(path)
        if not path.exists():
            return cls.empty()
        obj: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return cls.empty()
        cache = {str(k): str(v) for k, v in obj.items()}
        return cls(cache=cache)

