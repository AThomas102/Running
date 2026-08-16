"""Unit tests for pure Intervals helpers (no network).

Covers ID, payload, and activity normalisation in ``running.intervals_lib``.
Live fetch/upsert/Garmin sync are out of scope.
"""

from __future__ import annotations

from datetime import date

import pytest

from running.intervals_lib import (
    event_payload_from_session,
    format_duration,
    is_ride,
    is_run,
    month_bounds,
    normalize_activity,
    session_uid,
    sessions_date_range,
    slugify,
    summarize,
)


def test_month_bounds_half_open() -> None:
    """Return half-open ``[start, end)`` month windows.

    Purpose:
        Activity fetch ranges must not double-count month boundaries.

    Remove when:
        Month bounding moves or becomes inclusive-end.
    """
    start, end = month_bounds("2026-08")
    assert start == date(2026, 8, 1)
    assert end == date(2026, 9, 1)
    start_dec, end_dec = month_bounds("2026-12")
    assert start_dec == date(2026, 12, 1)
    assert end_dec == date(2027, 1, 1)
    with pytest.raises(ValueError, match="YYYY-MM"):
        month_bounds("2026-8")
    with pytest.raises(ValueError, match="Invalid month"):
        month_bounds("2026-13")


def test_slugify_and_session_uid_stable() -> None:
    """Keep ``running-repo:`` external IDs stable across upserts.

    Purpose:
        Stable IDs update events instead of duplicating them.

    Remove when:
        The UID scheme is replaced.
    """
    assert slugify("Easy 15k + strides") == "easy-15k-strides"
    assert slugify("  ") == "session"
    uid = session_uid(
        "2026-08-10-week",
        {"date": "2026-08-11", "name": "Easy 16k + strides"},
    )
    assert uid == "running-repo:2026-08-10-week:2026-08-11:easy-16k-strides"


def test_event_payload_from_session_normalizes_time_and_description() -> None:
    """Normalise local start times and bare Run zones for Garmin.

    Purpose:
        Payloads need ``HH:MM:SS`` starts and ``Z2 HR`` (not bare ``Z2``).

    Remove when:
        Payload shape changes.
    """
    payload = event_payload_from_session(
        {
            "date": "2026-08-11",
            "name": "Easy",
            "type": "Run",
            "start_time": "08:00",
            "description": "- 5km Z2\n",
        },
        uid="running-repo:test:2026-08-11:easy",
    )
    assert payload["start_date_local"] == "2026-08-11T08:00:00"
    assert payload["category"] == "WORKOUT"
    assert payload["external_id"] == "running-repo:test:2026-08-11:easy"
    assert "Z2 HR" in payload["description"]

    with pytest.raises(ValueError, match="date"):
        event_payload_from_session(
            {"name": "Easy", "type": "Run", "description": "- 1km Z2 HR\n"},
            uid="x",
        )


def test_is_run_and_is_ride_classification() -> None:
    """Classify Run vs Ride and exclude hybrids.

    Purpose:
        Month summaries and filters must not mis-count mixed types.

    Remove when:
        Intervals type taxonomy handling is rewritten.
    """
    assert is_run("Run") is True
    assert is_run("VirtualRun") is True
    assert is_run("Run_Bike") is False
    assert is_ride("Ride") is True
    assert is_ride("VirtualRide") is True
    assert is_ride("Run") is False


def test_normalize_activity_converts_metres_to_km() -> None:
    """Convert Intervals metre distances to planning kilometres.

    Purpose:
        Planning and summaries use km, not metres.

    Remove when:
        The API already returns km.
    """
    out = normalize_activity(
        {
            "id": 1,
            "name": "Easy",
            "type": "Run",
            "distance": 15000,
            "start_date_local": "2026-08-10T08:00:00",
            "moving_time": 3600,
        }
    )
    assert out["distance_km"] == 15.0
    assert out["moving_time_s"] == 3600
    assert out["type"] == "Run"


def test_summarize_splits_run_ride_other() -> None:
    """Split month totals by run/ride/other and track longest run.

    Purpose:
        Load evidence for planning depends on these summary fields.

    Remove when:
        Summarize metrics change.
    """
    activities = [
        {"type": "Run", "distance_km": 10.0},
        {"type": "Run", "distance_km": 16.5},
        {"type": "Ride", "distance_km": 20.0},
        {"type": "WeightTraining", "distance_km": 0.0},
    ]
    summary = summarize(activities)
    assert summary["run_sessions"] == 2
    assert summary["run_km"] == 26.5
    assert summary["ride_km"] == 20.0
    assert summary["longest_run_km"] == 16.5
    assert summary["activity_count"] == 4


def test_format_duration() -> None:
    """Format durations as M:SS or H:MM:SS; None as empty.

    Purpose:
        Human-readable duration strings in month markdown.

    Remove when:
        Duration formatting is unused.
    """
    assert format_duration(None) == ""
    assert format_duration(65) == "1:05"
    assert format_duration(3661) == "1:01:01"


def test_sessions_date_range() -> None:
    """Return min/max session dates for upload safety.

    Purpose:
        Clear/push ranges are derived from session date bounds.

    Remove when:
        Range helpers are inlined elsewhere.
    """
    assert sessions_date_range([]) is None
    rng = sessions_date_range(
        [
            {"date": "2026-08-15"},
            {"date": "2026-08-10"},
            {"date": "2026-08-12"},
        ]
    )
    assert rng == ("2026-08-10", "2026-08-15")
