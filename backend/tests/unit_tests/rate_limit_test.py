import pytest
from fastapi import HTTPException

from bracket.utils.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=3, window_seconds=60, clock=clock)
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("b")  # Other keys have their own window

    clock.now += 59.9
    assert not limiter.allow("a")
    clock.now += 0.2  # The first three hits are out of the window now
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]


def test_check_raises_429_and_idle_keys_are_forgotten() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_seconds=10, clock=clock)
    limiter.check("a")
    with pytest.raises(HTTPException) as error:
        limiter.check("a")
    assert error.value.status_code == 429

    clock.now += 11
    limiter.forget_idle(clock.now)
    assert limiter.hits == {}
