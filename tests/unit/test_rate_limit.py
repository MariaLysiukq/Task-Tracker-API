"""Unit tests for ``app.core.rate_limit``."""

import pytest

from app.core import rate_limit
from app.core.rate_limit import RateLimiter


class FakeClock:
    """Manually advanced time source.

    Parameters
    ----------
    now : float
        Initial time in seconds.
    """

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        """Return the current fake time.

        Returns
        -------
        float
            Current time in seconds.
        """
        return self.now


def test_allows_up_to_limit_then_blocks() -> None:
    """The first ``max_requests`` hits pass, the next one is rejected."""
    limiter = RateLimiter(3, 60, clock=FakeClock())
    assert [limiter.hit("a") for _ in range(4)] == [True, True, True, False]


def test_window_slides_and_rejections_are_not_counted() -> None:
    """Old hits expire one by one; rejected hits do not extend the block."""
    clock = FakeClock()
    limiter = RateLimiter(2, 60, clock=clock)
    assert limiter.hit("a")
    clock.now = 30
    assert limiter.hit("a")
    assert not limiter.hit("a")
    clock.now = 59.9
    assert not limiter.hit("a")
    clock.now = 60
    assert limiter.hit("a")
    assert not limiter.hit("a")
    clock.now = 90
    assert limiter.hit("a")


def test_keys_are_counted_separately() -> None:
    """One client reaching the limit does not block another."""
    limiter = RateLimiter(1, 60, clock=FakeClock())
    assert limiter.hit("a")
    assert not limiter.hit("a")
    assert limiter.hit("b")


def test_full_limiter_drops_stale_keys_first(monkeypatch: pytest.MonkeyPatch) -> None:
    """At the key cap, clients without recent hits are forgotten, active ones kept."""
    monkeypatch.setattr(rate_limit, "RATE_LIMIT_MAX_TRACKED_KEYS", 2)
    clock = FakeClock()
    limiter = RateLimiter(1, 60, clock=clock)
    limiter.hit("stale")
    clock.now = 61
    limiter.hit("active")
    assert limiter.hit("new")
    assert not limiter.hit("active")
    assert limiter.hit("stale")


def test_full_limiter_evicts_oldest_when_all_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """If every tracked client is active, the oldest one is dropped to stay within the cap."""
    monkeypatch.setattr(rate_limit, "RATE_LIMIT_MAX_TRACKED_KEYS", 2)
    limiter = RateLimiter(1, 60, clock=FakeClock())
    limiter.hit("first")
    limiter.hit("second")
    assert limiter.hit("third")
    assert not limiter.hit("second")
    assert limiter.hit("first")
