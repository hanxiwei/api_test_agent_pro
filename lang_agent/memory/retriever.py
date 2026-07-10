from __future__ import annotations

from .long_memory import LongMemory


def retrieve_few_shot_examples(
    long_memory: LongMemory | None,
    *,
    error_type: str,
    error_signature: str = "",
    k: int = 3,
) -> list[str]:
    if long_memory is None:
        return []
    return long_memory.retrieve_few_shots(error_type=error_type, error_signature=error_signature, k=k)
