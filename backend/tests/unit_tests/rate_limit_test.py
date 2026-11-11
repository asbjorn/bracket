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


def test_check_raises_429() -> None:
    limiter = SlidingWindowLimiter(limit=1, window_seconds=10, clock=FakeClock())
    limiter.check("a")
    with pytest.raises(HTTPException) as error:
        limiter.check("a")
    assert error.value.status_code == 429


def test_number_of_keys_is_bounded() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=5, window_seconds=60, max_keys=100, clock=clock)
    for index in range(1000):
        limiter.allow(f"key{index}")
        assert len(limiter.hits) <= 100
    # The least recently used keys went first
    assert "key999" in limiter.hits
    assert "key0" not in limiter.hits


def test_recently_used_keys_stay_and_idle_keys_are_dropped_first() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(
        limit=2, window_seconds=60, max_keys=3, cleanup_seconds=5, clock=clock
    )
    limiter.allow("old")
    clock.now += 61  # "old" is idle now
    limiter.allow("busy")
    limiter.allow("other")
    limiter.allow("busy")  # Used again: most recently used
    assert not limiter.allow("busy")

    limiter.allow("new")  # Full: the idle key goes, "busy" keeps its count
    assert set(limiter.hits) == {"busy", "other", "new"}
    assert not limiter.allow("busy")
