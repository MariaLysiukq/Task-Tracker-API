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


def to_utc(moment: datetime) -> datetime:
    """Convert a timezone-aware datetime to UTC.

    Parameters
    ----------
    moment : datetime
        Aware datetime in any timezone.

    Returns
    -------
    datetime
        The same instant with ``tzinfo=UTC``.

    Raises
    ------
    ValueError
        If ``moment`` is naive.
    """
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return moment.astimezone(UTC)
