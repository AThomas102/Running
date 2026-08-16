"""Unit tests for week YAML load, totals, sessions, and path resolution.

Guards plan SSOT contracts in ``running.week_plan`` offline. Shrink or drop
tests only when the matching API or athlete policy is intentionally retired.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from running.week_plan import (
    bike_session_from_day,
    covers_from_week,
    find_current_week_yaml,
    load_week_yaml,
    resolve_week_yaml,
    sessions_from_week,
    sum_run_km,
    validate_week_totals,
)
from running.workout_syntax import easy_run_description

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "weeks"


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
                "description": "",
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
        Enforce the AGENTS arithmetic check on week YAML.

    Remove when:
        Week plans stop using ``run_total_km``.
    """
    week = yaml.safe_load((FIXTURES / "valid-week.yaml").read_text(encoding="utf-8"))
    assert sum_run_km(week) == pytest.approx(42.0)
    validate_week_totals(week)


def test_validate_week_totals_rejects_mismatch() -> None:
    """Raise when claimed totals disagree with day distances.

    Purpose:
        Prevent shipping inconsistent YAML by surfacing both numbers.

    Remove when:
        Totals validation moves elsewhere.
    """
    week = yaml.safe_load(
        (FIXTURES / "mismatched-total-week.yaml").read_text(encoding="utf-8")
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


def test_load_week_yaml_rejects_bad_root_or_days(tmp_path: Path) -> None:
    """Reject non-mapping roots and YAML without a ``days`` list.

    Purpose:
        Keep the loader schema strict.

    Remove when:
        The loader schema changes.
    """
    bad_root = tmp_path / "list.yaml"
    bad_root.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_week_yaml(bad_root)

    no_days = tmp_path / "no-days.yaml"
    no_days.write_text("week_start: 2026-09-07\nrun_total_km: 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="days"):
        load_week_yaml(no_days)


def test_load_week_yaml_rejects_mismatched_fixture() -> None:
    """Refuse mismatched fixtures via load-time validation.

    Purpose:
        ``load_week_yaml`` must not return arithmetically invalid weeks.

    Remove when:
        Load no longer validates totals.
    """
    with pytest.raises(ValueError, match="run_total_km"):
        load_week_yaml(FIXTURES / "mismatched-total-week.yaml")


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
    """Map runnable kinds with distance to Run sessions; skip rest.

    Purpose:
        Only uploadable run kinds become calendar sessions.

    Remove when:
        Upload session mapping is redesigned.
    """
    week = {
        "week_start": "2026-09-07",
        "run_total_km": 30,
        "days": [
            {
                "date": "2026-09-07",
                "run_km": 10,
                "run_kind": "easy",
                "run_name": "Easy 10k",
                "description": "- 10km 8:00-4:40/km Pace\n",
            },
            {"date": "2026-09-08", "run_km": 0, "run_kind": "rest"},
            {
                "date": "2026-09-09",
                "run_km": 8,
                "run_kind": "interval",
                "run_name": "Intervals",
                "description": "- 8km Z4 HR\n",
            },
            {
                "date": "2026-09-10",
                "run_km": 12,
                "run_kind": "long",
                "run_name": "Long 12k",
                "description": "- 12km 8:00-4:40/km Pace\n",
            },
        ],
    }
    sessions = sessions_from_week(week)
    kinds = [s["kind"] for s in sessions]
    assert kinds == ["easy", "interval", "long"]
    assert all(s["type"] == "Run" for s in sessions)
    assert "rest" not in kinds


def test_sessions_from_week_default_easy_description_is_pace_band() -> None:
    """Default empty easy/long descriptions to the athlete Pace band.

    Purpose:
        Easy defaults must be Pace, not HR.

    Remove when:
        Default easy target policy changes.
    """
    week = _minimal_week(run_total_km=12)
    sessions = sessions_from_week(week)
    assert len(sessions) == 1
    assert sessions[0]["description"] == easy_run_description(12)
    assert "8:00-4:40/km Pace" in sessions[0]["description"]
    assert "% HR" not in sessions[0]["description"]


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


def test_resolve_week_yaml_newest_and_by_date(tmp_path: Path) -> None:
    """Resolve newest week by filename date, or an explicit Monday date.

    Purpose:
        Plan discovery must pick the current week and allow date lookup.

    Remove when:
        Plan discovery rules change.
    """
    plans = tmp_path / "plans"
    plans.mkdir()
    older = plans / "2026-08-03-week.yaml"
    newer = plans / "2026-08-10-week.yaml"
    older.write_text(
        "week_start: 2026-08-03\nrun_total_km: 0\ndays: []\n", encoding="utf-8"
    )
    newer.write_text(
        "week_start: 2026-08-10\nrun_total_km: 0\ndays: []\n", encoding="utf-8"
    )

    assert find_current_week_yaml(plans) == newer
    assert resolve_week_yaml(None, root=tmp_path) == newer
    assert resolve_week_yaml("2026-08-03", root=tmp_path) == older
    with pytest.raises(FileNotFoundError):
        resolve_week_yaml("2026-01-01", root=tmp_path)
