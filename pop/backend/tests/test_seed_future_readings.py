"""Tests for historical seed timestamp safety."""

from datetime import datetime, timedelta, timezone

from seed import clamp_seed_timestamp


def test_seed_timestamp_is_clamped_to_past() -> None:
    now = datetime(2026, 11, 24, 10, 30, 0, tzinfo=timezone.utc)
    future = datetime(2026, 11, 24, 16, 30, 0, tzinfo=timezone.utc)

    clamped = clamp_seed_timestamp(future, now)

    assert clamped <= now - timedelta(minutes=1)
    assert clamped == now - timedelta(minutes=1)
