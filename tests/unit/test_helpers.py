"""Unit tests for ``app._detail.helpers``."""

from datetime import UTC, datetime, timedelta

from app._detail.helpers import utc_now


def test_utc_now_is_timezone_aware_utc() -> None:
    """``utc_now`` returns an aware datetime with zero UTC offset."""
    now = utc_now()
    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


def test_utc_now_matches_current_time() -> None:
    """``utc_now`` is comparable with other aware datetimes and is current."""
    before = datetime.now(UTC)
    now = utc_now()
    after = datetime.now(UTC)
    assert before <= now <= after
