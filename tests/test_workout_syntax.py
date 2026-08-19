"""Tests for Intervals.icu workout description string generation.

Covers ``running.workout_syntax`` formatting and guide checks used by week
plans. Shrink when helpers move or Intervals syntax support is retired.

Syntax reference:
https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701
"""

from __future__ import annotations

import pytest

from running.workout_syntax import (
    SYNTAX_GUIDE_URL,
    assert_description_follows_guide,
    easy_bike_description,
    easy_run_description,
    extract_step_loads_and_targets,
    format_distance_km,
    format_duration_minutes,
    format_hr_pct_target,
    intensity_step_line,
    normalize_workout_description,
    step_line,
)


def test_syntax_guide_url_is_official_forum_doc() -> None:
    """Pin the official Intervals workout-builder guide URL.

    Purpose:
        Generated syntax must track the documented guide.

    Remove when:
        Syntax is no longer generated from that guide.
    """
    assert "workout-builder-syntax-quick-guide" in SYNTAX_GUIDE_URL
    assert SYNTAX_GUIDE_URL.startswith("https://forum.intervals.icu/")


def test_format_hr_pct_target_matches_guide_examples() -> None:
    """Format ``% HR`` targets like the Intervals guide examples.

    Purpose:
        Emitted HR strings must match guide forms.

    Remove when:
        HR % targets are no longer emitted.
    """
    assert format_hr_pct_target(70, 70) == "70% HR"
    assert format_hr_pct_target(75, 80) == "75-80% HR"
    assert format_hr_pct_target(41, 72) == "41-72% HR"


def test_easy_run_description_is_guide_compatible() -> None:
    """Build easy runs as an explicit Pace band, not HR.

    Purpose:
        Easy effort is Pace-governed; numbers are caller-supplied.

    Remove when:
        Easy runs stop using absolute Pace bands.
    """
    desc = easy_run_description(12, pace_ceiling="8:00", pace_floor="5:30")
    assert desc == "- 12km 8:00-5:30/km Pace\n"
    assert_description_follows_guide(desc)
    load, target = extract_step_loads_and_targets(desc)[0]
    assert load == "12km"
    assert target == "8:00-5:30/km Pace"
    assert "% HR" not in desc
    assert "bpm" not in desc.lower()


def test_intensity_step_line_press_lap() -> None:
    """Encode open lap-button rest as ``Press lap`` plus intensity=rest.

    Purpose:
        Watch-friendly relocating rest before repeats.

    Remove when:
        Press-lap encoding is retired.
    """
    line = intensity_step_line("15m", "rest", press_lap=True)
    assert line == "- Press lap 15m intensity=rest\n"


def test_absolute_bpm_target_rejected_by_step_builder() -> None:
    """Reject absolute bpm targets not in the Intervals guide.

    Purpose:
        Structured targets must stay guide-compatible.

    Remove when:
        ``step_line`` validation is removed or the guide adds bpm targets.
    """
    with pytest.raises(ValueError, match="supported structured target"):
        step_line("12km", "80-140 HR")
    with pytest.raises(ValueError, match="supported structured target"):
        step_line("12km", "80-140bpm HR")


def test_easy_bike_description_uses_zone_hr() -> None:
    """Encode bike length with documented ``Z2 HR``.

    Purpose:
        Simple bike defaults stay guide-compatible.

    Remove when:
        Bike defaults change away from Z2 HR.
    """
    by_min = easy_bike_description(minutes=90)
    assert by_min == "- 1h30m Z2 HR\n"
    assert_description_follows_guide(by_min)
    by_km = easy_bike_description(km=25)
    assert by_km == "- 25km Z2 HR\n"
    assert_description_follows_guide(by_km)


def test_duration_and_distance_tokens() -> None:
    """Format duration and distance tokens per the guide.

    Purpose:
        ``m`` means minutes and ``km`` means distance in step loads.

    Remove when:
        Format helpers are deleted.
    """
    assert format_duration_minutes(45) == "45m"
    assert format_duration_minutes(90) == "1h30m"
    assert format_duration_minutes(60) == "1h"
    assert format_distance_km(10) == "10km"
    assert format_distance_km(10.5) == "10.5km"


def test_normalize_bare_zone_on_run() -> None:
    """Expand bare ``Z2`` on Run to ``Z2 HR``.

    Purpose:
        Garmin-safe zone targets on run workouts.

    Remove when:
        Zone normalization is retired.
    """
    out = normalize_workout_description("- 5km Z2\n", sport="Run")
    assert "Z2 HR" in out
