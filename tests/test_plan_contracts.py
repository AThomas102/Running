"""Regression contracts for session shape and week-plan fixtures.

Fail loudly if plans drift from structured sessions and athlete-owned Pace.
Do not lock one athlete's numbers into the package.
"""

from __future__ import annotations

import json
from pathlib import Path

from running.athlete import load_athlete_anchors
from running.session import RunSession
from running.week import load_week, plans_dir, render_week_markdown
from running.workout_syntax import assert_description_follows_guide

FIXTURES = Path(__file__).resolve().parent / "fixtures"
WEEKS = FIXTURES / "weeks"


def _is_legacy_description_week(raw: dict) -> bool:
    """Return True if a week still uses hand-written day descriptions."""
    for day in raw.get("days") or []:
        if isinstance(day, dict) and day.get("description") and not day.get("run"):
            return True
    return False


def test_live_week_json_totals_match_day_sums() -> None:
    """Validate live ``*-week.json`` that already use structured ``run``.

    Purpose:
        Catch plan arithmetic drift before upload/render.

    Remove when:
        Week JSON totals are no longer required.
    """
    plans = plans_dir()
    weeks = sorted(plans.glob("*-week.json"))
    for path in weeks:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        if _is_legacy_description_week(raw):
            continue
        load_week(path)


def test_fixture_easy_resolves_athlete_pace_not_hr() -> None:
    """Require easy/long generated targets to use athlete Pace, not ``% HR``.

    Purpose:
        Easy guidance is Pace-based via athlete JSON.

    Remove when:
        Easy guidance returns to HR by policy.
    """
    week = load_week(WEEKS / "valid-week.json", root=FIXTURES)
    anchors = load_athlete_anchors("athletes/sample.json", root=FIXTURES)
    checked = 0
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        kind = str(day.get("run_kind") or "").lower()
        km = float(day.get("run_km") or 0)
        raw = day.get("run")
        if kind in {"easy", "long"} and km > 0 and isinstance(raw, dict):
            desc = RunSession.from_dict(raw).to_intervals_description(anchors)
            assert "Pace" in desc, f"{day.get('date')}: expected Pace target"
            assert "% HR" not in desc, f"{day.get('date')}: must not use % HR for easy"
            assert anchors.easy_pace_target() in desc
            assert_description_follows_guide(desc)
            checked += 1
    assert checked >= 1


def test_fixture_stride_session_round_trips_press_lap_and_reps() -> None:
    """Round-trip a press-lap + repeat stride structure from the fixture.

    Purpose:
        Watch-friendly stride *shape* (open lap rest, Nx inner steps).

    Remove when:
        Stride watch structure is redesigned.
    """
    week = load_week(WEEKS / "valid-week.json", root=FIXTURES)
    anchors = load_athlete_anchors("athletes/sample.json", root=FIXTURES)
    stride_days = []
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        name = str(day.get("run_name") or "").lower()
        if "stride" in name and isinstance(day.get("run"), dict):
            stride_days.append(day)
    assert stride_days, "fixture week should include at least one stride session"
    for day in stride_days:
        session = RunSession.from_dict(day["run"])
        assert session.has_press_lap()
        desc = session.to_intervals_description(anchors)
        assert "Press lap" in desc
        assert "x\n" in desc or "\nx" in desc or "4x" in desc
        assert_description_follows_guide(desc)


def test_copy_paste_summary_appends_strides() -> None:
    """Include ``+ strides`` in the copy-paste summary when a day has strides.

    Purpose:
        Chat paste must match JSON stride sessions.

    Remove when:
        Copy-paste summary no longer lists day sessions.
    """
    week = load_week(WEEKS / "valid-week.json", root=FIXTURES)
    anchors = load_athlete_anchors("athletes/sample.json", root=FIXTURES)
    text = render_week_markdown(
        week, source_name="valid-week.json", anchors=anchors
    )
    assert "12k easy + strides" in text
    assert "12 easy + strides" in text
    assert "Press lap" in text
