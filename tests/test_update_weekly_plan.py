"""Unit tests for calendar upload safety and dry-run session push.

Locks past-day protection and dry-run UID behaviour in
``running.update_weekly_plan`` without calling Intervals.
"""

from __future__ import annotations

from datetime import date
from io import StringIO
from contextlib import redirect_stdout

import pytest

from running.intervals_lib import session_uid
from running.update_weekly_plan import (
    clamp_clear_range,
    partition_sessions,
    push_sessions,
    refuse_past_plan,
)


TODAY = date(2026, 8, 10)


def test_refuse_past_plan_when_coverage_ends_before_today() -> None:
    """Refuse upload when week coverage already ended.

    Purpose:
        Never re-upload a finished week.

    Remove when:
        Past weeks become intentionally re-uploadable.
    """
    meta = {"week_start": "2026-07-27", "days": [{"date": "2026-07-27"}]}
    sessions = [{"date": "2026-07-27", "name": "Easy", "kind": "easy"}]
    with pytest.raises(SystemExit, match="Refusing upload"):
        refuse_past_plan(meta, sessions, today=TODAY)


def test_refuse_past_plan_allows_current_week() -> None:
    """Allow a week that still includes today.

    Purpose:
        Current-week uploads must not be blocked by refuse rules.

    Remove when:
        Refuse rules change.
    """
    meta = {
        "week_start": "2026-08-10",
        "days": [{"date": "2026-08-10"}, {"date": "2026-08-16"}],
    }
    sessions = [
        {"date": "2026-08-10", "name": "Easy", "kind": "easy"},
        {"date": "2026-08-15", "name": "Long", "kind": "long"},
    ]
    refuse_past_plan(meta, sessions, today=TODAY)


def test_clamp_clear_range_never_before_today() -> None:
    """Clamp managed-event clears so they never start before today.

    Purpose:
        Past calendar days must not be cleared or rewritten.

    Remove when:
        Clear policy changes.
    """
    assert clamp_clear_range("2026-08-10", "2026-08-16", today=TODAY) == (
        "2026-08-10",
        "2026-08-16",
    )
    assert clamp_clear_range("2026-08-01", "2026-08-16", today=TODAY) == (
        "2026-08-10",
        "2026-08-16",
    )
    assert clamp_clear_range("2026-07-01", "2026-07-31", today=TODAY) is None


def test_partition_sessions_splits_on_today() -> None:
    """Split sessions into before-today vs today-or-later.

    Purpose:
        Past sessions stay local; only today+ are uploadable.

    Remove when:
        Partition semantics change.
    """
    sessions = [
        {"date": "2026-08-09", "name": "Past"},
        {"date": "2026-08-10", "name": "Today"},
        {"date": "2026-08-11", "name": "Future"},
    ]
    past, future = partition_sessions(sessions, today=TODAY)
    assert [s["name"] for s in past] == ["Past"]
    assert [s["name"] for s in future] == ["Today", "Future"]


def test_push_sessions_dry_run_skips_past_and_builds_uids() -> None:
    """Skip past days in dry-run and build stable ``running-repo:`` IDs.

    Purpose:
        Dry-run must count future sessions only and keep upsert IDs stable.

    Remove when:
        UID scheme or skip policy changes.
    """
    sessions = [
        {
            "date": "2026-08-09",
            "name": "Easy 10k",
            "kind": "easy",
            "type": "Run",
            "description": "- 10km 8:00-4:40/km Pace\n",
        },
        {
            "date": "2026-08-11",
            "name": "Easy 12k",
            "kind": "easy",
            "type": "Run",
            "start_time": "08:00",
            "description": "- 12km 8:00-4:40/km Pace\n",
        },
    ]
    buf = StringIO()
    with redirect_stdout(buf):
        n = push_sessions(
            "unused-key",
            sessions,
            plan_stem="2026-08-10-week",
            intervals_only=False,
            dry_run=True,
            garmin_sync=False,
            today=TODAY,
        )
    out = buf.getvalue()
    assert n == 1
    assert "skip past day 2026-08-09" in out
    assert "dry-run 2026-08-11" in out
    uid = session_uid(
        "2026-08-10-week",
        {"date": "2026-08-11", "name": "Easy 12k"},
    )
    assert uid == "running-repo:2026-08-10-week:2026-08-11:easy-12k"
    assert uid in out


def test_push_sessions_intervals_only_filters_kinds() -> None:
    """Upload only ``kind=interval`` when ``intervals_only`` is set.

    Purpose:
        Honour the ``--intervals-only`` CLI filter.

    Remove when:
        That CLI flag is removed.
    """
    sessions = [
        {
            "date": "2026-08-11",
            "name": "Easy",
            "kind": "easy",
            "type": "Run",
            "description": "- 10km 8:00-4:40/km Pace\n",
        },
        {
            "date": "2026-08-12",
            "name": "Track",
            "kind": "interval",
            "type": "Run",
            "description": "- 1km Z4 HR\n",
        },
    ]
    buf = StringIO()
    with redirect_stdout(buf):
        n = push_sessions(
            "unused-key",
            sessions,
            plan_stem="2026-08-10-week",
            intervals_only=True,
            dry_run=True,
            garmin_sync=False,
            today=TODAY,
        )
    assert n == 1
    assert "skip" in buf.getvalue()
    assert "Track" in buf.getvalue() or "interval" in buf.getvalue().lower()


def test_push_sessions_refuses_when_nothing_left() -> None:
    """Refuse upload when every session is in the past.

    Purpose:
        Empty/all-past pushes must not call Intervals.

    Remove when:
        Empty pushes become allowed.
    """
    sessions = [
        {
            "date": "2026-08-01",
            "name": "Old",
            "kind": "easy",
            "type": "Run",
            "description": "- 5km 8:00-4:40/km Pace\n",
        }
    ]
    with pytest.raises(SystemExit, match="no sessions on or after today"):
        push_sessions(
            "unused-key",
            sessions,
            plan_stem="2026-08-10-week",
            intervals_only=False,
            dry_run=True,
            garmin_sync=False,
            today=TODAY,
        )
