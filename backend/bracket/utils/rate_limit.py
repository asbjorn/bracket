"""
A small in-process sliding-window rate limiter, for public endpoints without an account
(e.g. result links). Per process: with several workers the limit applies per worker.
"""

import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException
from starlette import status

MAX_KEYS = 10_000


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        """Records a hit for `key`; `False` when the key already had `limit` hits in the window."""
        now = self.clock()
        if len(self.hits) > MAX_KEYS:
            self.forget_idle(now)
        hits = self.hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def forget_idle(self, now: float) -> None:
        self.hits = {
            key: hits
            for key, hits in self.hits.items()
            if hits and hits[-1] > now - self.window_seconds
        }

    def check(self, key: str) -> None:
        if not self.allow(key):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, please wait a moment and try again",
            )
