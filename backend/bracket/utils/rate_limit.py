"""
A small in-process sliding-window rate limiter, for public endpoints without an account
(e.g. result links). Per process: with several workers the limit applies per worker.

Memory is bounded: at most `max_keys` keys are kept. Idle keys are dropped at most every
`cleanup_seconds`; when still full, the least recently used keys are evicted.
"""

import time
from collections import OrderedDict, deque
from collections.abc import Callable

from fastapi import HTTPException
from starlette import status

MAX_KEYS = 10_000


class SlidingWindowLimiter:
    def __init__(  # pylint: disable=too-many-arguments
        self,
        limit: int,
        window_seconds: float,
        *,
        max_keys: int = MAX_KEYS,
        cleanup_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.cleanup_seconds = cleanup_seconds
        self.clock = clock
        self.hits: OrderedDict[str, deque[float]] = OrderedDict()
        self.last_cleanup = clock()

    def allow(self, key: str) -> bool:
        """Records a hit for `key`; `False` when the key already had `limit` hits in the window."""
        now = self.clock()
        hits = self.hits.get(key)
        if hits is None:
            self.make_room(now)
            hits = self.hits[key] = deque()
        else:
            self.hits.move_to_end(key)
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def make_room(self, now: float) -> None:
        """Room for one more key: drop idle keys (not too often), then the least recently used."""
        if len(self.hits) < self.max_keys:
            return
        if now - self.last_cleanup >= self.cleanup_seconds:
            self.forget_idle(now)
        while len(self.hits) >= self.max_keys:
            self.hits.popitem(last=False)

    def forget_idle(self, now: float) -> None:
        self.last_cleanup = now
        for key in [
            k for k, hits in self.hits.items() if not hits or hits[-1] <= now - self.window_seconds
        ]:
            del self.hits[key]

    def check(self, key: str) -> None:
        if not self.allow(key):
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, please wait a moment and try again",
            )
