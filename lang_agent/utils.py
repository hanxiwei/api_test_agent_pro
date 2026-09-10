from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any


class BaseSelfHealingError(Exception):
    def __init__(self, message: str, *, user_hint: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.user_hint = user_hint
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "user_hint": self.user_hint,
            "details": self.details,
        }


class LLMUnavailableError(BaseSelfHealingError):
    pass


class OpenAPIParserError(BaseSelfHealingError):
    pass


class TestRunnerError(BaseSelfHealingError):
    pass


class DiagnosisBlockedError(BaseSelfHealingError):
    pass


class RepairGateBlockedError(BaseSelfHealingError):
    pass


def atomic_write_text(target: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=str(target_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, target_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target_path
