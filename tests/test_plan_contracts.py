"""Regression contracts for easy-pace policy and week-plan fixtures.

Fail loudly if plans or defaults drift from intended Pace / stride structure.
Do not weaken these to match broken plans — fix the plan or code instead.
"""

from __future__ import annotations

from pathlib import Path

from running.week_plan import load_week, plans_dir, render_week_markdown
from running.workout_syntax import EASY_PACE_FLOOR, easy_run_description

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "weeks"


def test_live_week_json_totals_match_day_sums() -> None:
    """Validate every live ``*-week.json`` when personal data is present.

    Purpose:
        Catch plan arithmetic drift before upload/render.

    Remove when:
        Week JSON totals are no longer required.
    """
    plans = plans_dir()
    weeks = sorted(plans.glob("*-week.json"))
    for path in weeks:
        load_week(path)


def test_easy_pace_floor_constant_is_4_40() -> None:
    """Keep easy Pace floor at 4:40/km (band 8:00–4:40).

    Purpose:
        Athlete easy policy is Pace-governed with a 4:40 floor.

    Remove when:
        The easy Pace band policy changes.
    """
    assert EASY_PACE_FLOOR == "4:40"
    desc = easy_run_description(1)
    assert desc == "- 1km 8:00-4:40/km Pace\n"


def test_fixture_stride_days_use_press_lap_and_reps() -> None:
    """Require stride days to use Press-lap rest then 4×20s / 90s.

    Purpose:
        Watch-friendly stride structure must stay consistent.

    Remove when:
        Stride watch structure is redesigned.
    """
    week = load_week(FIXTURES / "valid-week.json")
    stride_days = []
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        blob = f"{day.get('run_name', '')}\n{day.get('description', '')}".lower()
        if "stride" in blob or "4x" in str(day.get("description") or "").lower():
            if "20s" in str(day.get("description") or ""):
                stride_days.append(day)
    assert stride_days, "fixture week should include at least one stride session"
    for day in stride_days:
        desc = str(day.get("description") or "")
        assert "Press lap" in desc
        assert "4x" in desc
        assert "20s" in desc
        assert "90s" in desc


def test_fixture_easy_long_use_pace_not_hr_percent() -> None:
    """Require easy/long targets to use Pace, not ``% HR``.

    Purpose:
        Easy guidance is Pace-based for this athlete.

    Remove when:
        Easy guidance returns to HR by policy.
    """
    week = load_week(FIXTURES / "valid-week.json")
    checked = 0
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        kind = str(day.get("run_kind") or "").lower()
        km = float(day.get("run_km") or 0)
        if kind in {"easy", "long"} and km > 0:
            desc = str(day.get("description") or "")
            assert "Pace" in desc, f"{day.get('date')}: expected Pace target"
            assert "% HR" not in desc, f"{day.get('date')}: must not use % HR for easy"
            checked += 1
    assert checked >= 1


def test_copy_paste_summary_appends_strides() -> None:
    """Include ``+ strides`` in the copy-paste summary when a day has strides.

    Purpose:
        Chat paste must match JSON stride sessions.

    Remove when:
        Copy-paste summary no longer lists day sessions.
    """
    week = load_week(FIXTURES / "valid-week.json")
    text = render_week_markdown(week, source_name="valid-week.json")
    assert "12k easy + strides" in text
    assert "12 easy + strides" in text
