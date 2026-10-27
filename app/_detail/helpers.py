"""Small internal helpers."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns
    -------
    datetime
        Current moment with ``tzinfo=UTC``.
    """
    return datetime.now(UTC)
