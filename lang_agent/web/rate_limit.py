from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Iterator
from contextlib import contextmanager

from ..core.utils import ConcurrencyLimitExceededError, RateLimitExceededError


class InMemoryRateLimiter:
    def __init__(self, *, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            bucket = self._events[key]
            while bucket and now - bucket[0] >= self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.max_calls:
                raise RateLimitExceededError(
                    f"请求频率超过限制：{self.max_calls}/{self.window_seconds}s",
                    user_hint="当前访问过于频繁，请稍后再试。",
                    details={
                        "key": key,
                        "max_calls": self.max_calls,
                        "window_seconds": self.window_seconds,
                    },
                )
            bucket.append(now)


class ConcurrencyGate:
    def __init__(self, *, max_concurrent: int) -> None:
        self.max_concurrent = max_concurrent
        self._semaphore = threading.BoundedSemaphore(max_concurrent)

    @contextmanager
    def slot(self, *, timeout: float | None = None) -> Iterator[None]:
        acquired = self._semaphore.acquire(timeout=timeout) if timeout is not None else self._semaphore.acquire()
        if not acquired:
            raise ConcurrencyLimitExceededError(
                "当前并发槽位已满",
                user_hint="当前已有较多任务在运行，请稍后重试。",
                details={"max_concurrent": self.max_concurrent, "timeout": timeout},
            )
        try:
            yield
        finally:
            self._semaphore.release()
