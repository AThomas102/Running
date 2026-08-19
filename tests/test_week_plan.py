"""Unit tests for week JSON load, totals, sessions, and path resolution.

Guards plan SSOT contracts in ``running.week`` offline.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from running.athlete import load_athlete_anchors
from running.week import (
    bike_session_from_day,
    covers_from_week,
    find_current_week_json,
    load_week,
    resolve_week_json,
    sessions_from_week,
    sum_run_km,
    validate_day_sessions,
    validate_week_totals,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WEEKS = FIXTURES / "weeks"


def _minimal_week(**overrides: object) -> dict:
    """Build a minimal in-memory week mapping for unit tests.

    Args:
        **overrides: Fields merged onto the default week dict.

    Returns:
        A week mapping suitable for unit tests.
    """
    week = {
        "week_start": "2026-09-07",
        "run_total_km": 12,
        "days": [
            {
                "date": "2026-09-07",
                "run_km": 12,
                "run_kind": "easy",
                "run_name": "Easy 12k",
                "start_time": "08:00",
                "run": {
                    "kind": "easy",
                    "blocks": [{"km": 12, "target": {"athlete": "easy_pace"}}],
                },
            },
            {
                "date": "2026-09-08",
                "run_km": 0,
                "run_kind": "rest",
            },
        ],
    }
    week.update(overrides)
    return week


def test_sum_and_validate_week_totals_match() -> None:
    """Require ``run_total_km`` to equal the sum of ``days[].run_km``.

    Purpose:
        Enforce the AGENTS arithmetic check on week JSON.

    Remove when:
        Week plans stop using ``run_total_km``.
    """
    week = json.loads((WEEKS / "valid-week.json").read_text(encoding="utf-8"))
    assert sum_run_km(week) == pytest.approx(42.0)
    validate_week_totals(week)


def test_validate_week_totals_rejects_mismatch() -> None:
    """Raise when claimed totals disagree with day distances.

    Purpose:
        Prevent shipping inconsistent JSON by surfacing both numbers.

    Remove when:
        Totals validation moves elsewhere.
    """
    week = json.loads(
        (WEEKS / "mismatched-total-week.json").read_text(encoding="utf-8")
    )
    with pytest.raises(ValueError, match=r"run_total_km \(99\).*days\[\].*run_km \(28\)"):
        validate_week_totals(week)


def test_validate_week_totals_requires_run_total_km() -> None:
    """Raise when ``run_total_km`` is missing.

    Purpose:
        Missing totals must be an error, not a silent skip.

    Remove when:
        Totals become optional by design.
    """
    week = _minimal_week()
    del week["run_total_km"]
    with pytest.raises(ValueError, match="missing run_total_km"):
        validate_week_totals(week)


def test_validate_day_sessions_rejects_run_km_vs_blocks() -> None:
    """Raise when day.run distance does not match ``run_km``.

    Purpose:
        Session blocks are the workout SSOT; ``run_km`` must agree.

    Remove when:
        ``run_km`` is derived only from the session.
    """
    week = _minimal_week(run_total_km=12)
    week["days"][0]["run_km"] = 12
    week["days"][0]["run"]["blocks"][0]["km"] = 10
    with pytest.raises(ValueError, match="session distance"):
        validate_day_sessions(week)


def test_load_week_rejects_bad_root_or_days(tmp_path: Path) -> None:
    """Reject non-object roots and JSON without a ``days`` list.

    Purpose:
        Keep the loader schema strict.

    Remove when:
        The loader schema changes.
    """
    bad_root = tmp_path / "list.json"
    bad_root.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_week(bad_root)

    no_days = tmp_path / "no-days.json"
    no_days.write_text(
        '{"week_start": "2026-09-07", "run_total_km": 0}\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="days"):
        load_week(no_days)


def test_load_week_rejects_mismatched_fixture() -> None:
    """Refuse mismatched fixtures via load-time validation.

    Purpose:
        ``load_week`` must not return arithmetically invalid weeks.

    Remove when:
        Load no longer validates totals.
    """
    with pytest.raises(ValueError, match="run_total_km"):
        load_week(WEEKS / "mismatched-total-week.json", root=FIXTURES)


def test_covers_from_week_is_mon_through_sun() -> None:
    """Cover exactly Monday through Sunday from ``week_start``.

    Purpose:
        Upload/clear ranges assume a 7-day calendar week.

    Remove when:
        Weeks stop being calendar weeks.
    """
    week = {"week_start": "2026-09-07", "run_total_km": 0, "days": []}
    oldest, newest = covers_from_week(week)
    assert oldest == "2026-09-07"
    assert newest == "2026-09-13"
    assert (date.fromisoformat(newest) - date.fromisoformat(oldest)).days == 6


def test_sessions_from_week_uploads_runs_and_skips_rest() -> None:
    """Map runnable kinds with a session to Run uploads; skip rest.

    Purpose:
        Only uploadable run kinds become calendar sessions.

    Remove when:
        Upload session mapping is redesigned.
    """
    anchors = load_athlete_anchors("athletes/sample.json", root=FIXTURES)
    week = {
        "week_start": "2026-09-07",
        "run_total_km": 30,
        "days": [
            {
                "date": "2026-09-07",
                "run_km": 10,
                "run_kind": "easy",
                "run_name": "Easy 10k",
                "run": {
                    "kind": "easy",
                    "blocks": [{"km": 10, "target": {"athlete": "easy_pace"}}],
                },
            },
            {"date": "2026-09-08", "run_km": 0, "run_kind": "rest"},
            {
                "date": "2026-09-09",
                "run_km": 8,
                "run_kind": "interval",
                "run_name": "Intervals",
                "run": {
                    "kind": "interval",
                    "blocks": [{"km": 8, "target": {"hr": "Z4 HR"}}],
                },
            },
            {
                "date": "2026-09-10",
                "run_km": 12,
                "run_kind": "long",
                "run_name": "Long 12k",
                "run": {
                    "kind": "long",
                    "blocks": [{"km": 12, "target": {"athlete": "easy_pace"}}],
                },
            },
        ],
    }
    sessions = sessions_from_week(week, anchors)
    kinds = [s["kind"] for s in sessions]
    assert kinds == ["easy", "interval", "long"]
    assert all(s["type"] == "Run" for s in sessions)
    assert "rest" not in kinds


def test_sessions_from_week_easy_uses_athlete_pace_band() -> None:
    """Generate easy/long descriptions from athlete JSON Pace bands.

    Purpose:
        Easy defaults must be Pace from the athlete file, not HR.

    Remove when:
        Easy target policy changes.
    """
    anchors = load_athlete_anchors("athletes/sample.json", root=FIXTURES)
    sessions = sessions_from_week(_minimal_week(), anchors)
    assert len(sessions) == 1
    desc = sessions[0]["description"]
    assert anchors.easy_pace_target() in desc
    assert "Pace" in desc
    assert "% HR" not in desc


def test_bike_session_from_day_prefers_bike_min() -> None:
    """Prefer ``bike_min`` over ``bike_km`` and encode rides as ``Z2 HR``.

    Purpose:
        Planned Ride length and target encoding stay stable.

    Remove when:
        Bike upload encoding changes.
    """
    day_min = {
        "date": "2026-09-07",
        "bike_min": 90,
        "bike_km": 40,
    }
    ride = bike_session_from_day(day_min)
    assert ride is not None
    assert ride["type"] == "Ride"
    assert ride["kind"] == "bike"
    assert "1h30m" in ride["description"]
    assert "Z2 HR" in ride["description"]

    day_km = {"date": "2026-09-07", "bike_km": 25}
    ride_km = bike_session_from_day(day_km)
    assert ride_km is not None
    assert "25km" in ride_km["description"]
    assert "Z2 HR" in ride_km["description"]

    assert bike_session_from_day({"date": "2026-09-07"}) is None


def test_resolve_week_json_newest_and_by_date(tmp_path: Path) -> None:
    """Resolve newest week by filename date, or an explicit Monday date.

    Purpose:
        Plan discovery must pick the current week and allow date lookup.

    Remove when:
        Plan discovery rules change.
    """
    plans = tmp_path / "plans"
    plans.mkdir()
    older = plans / "2026-08-03-week.json"
    newer = plans / "2026-08-10-week.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")

    assert find_current_week_json(plans) == newer
    assert resolve_week_json(None, root=tmp_path) == newer
    assert resolve_week_json("2026-08-03", root=tmp_path) == older
    with pytest.raises(FileNotFoundError):
        resolve_week_json("2026-01-01", root=tmp_path)
