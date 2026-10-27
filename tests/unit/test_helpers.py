"""Unit tests for ``app._detail.helpers``."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app._detail.helpers import to_utc, utc_now


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


def test_to_utc_converts_offset_to_utc() -> None:
    """``to_utc`` keeps the instant and switches the timezone to UTC."""
    local = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=2)))
    converted = to_utc(local)
    assert converted == local
    assert converted.tzinfo is UTC
    assert converted.hour == 10


def test_to_utc_rejects_naive_datetime() -> None:
    """``to_utc`` refuses naive datetimes."""
    with pytest.raises(ValueError, match="timezone-aware"):
        to_utc(datetime(2026, 1, 1, 12))
