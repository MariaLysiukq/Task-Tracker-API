"""In-memory sliding-window rate limiter.

Counts live in the process memory: each worker counts on its own and counts
reset on restart. Running several workers or instances needs a shared store
(e.g. Redis) instead.
"""

import time
from collections import deque
from collections.abc import Callable

from app._detail.constants import RATE_LIMIT_MAX_TRACKED_KEYS


class RateLimiter:
    """Allow at most ``max_requests`` per key within a sliding time window.

    Parameters
    ----------
    max_requests : int
        Requests allowed per key within the window.
    window_seconds : float
        Window length in seconds.
    clock : Callable[[], float]
        Monotonic time source in seconds; replaceable in tests.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> bool:
        """Record a request for ``key`` if it is within the limit.

        Rejected requests are not recorded, so a blocked client regains access
        once its earlier requests leave the window.

        Parameters
        ----------
        key : str
            Client identifier, e.g. its IP address.

        Returns
        -------
        bool
            ``True`` if the request is allowed, ``False`` if the limit is reached.
        """
        now = self._clock()
        cutoff = now - self.window_seconds
        if key not in self._hits and len(self._hits) >= RATE_LIMIT_MAX_TRACKED_KEYS:
            self._make_room(cutoff)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def _make_room(self, cutoff: float) -> None:
        """Bound memory: drop keys with no recent requests, then the oldest keys.

        Parameters
        ----------
        cutoff : float
            Requests at or before this time are outside the window.
        """
        self._hits = {key: hits for key, hits in self._hits.items() if hits and hits[-1] > cutoff}
        while len(self._hits) >= RATE_LIMIT_MAX_TRACKED_KEYS:
            del self._hits[next(iter(self._hits))]
