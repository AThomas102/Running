"""
Tests for Intervals.icu activity/workout description string generation.

Syntax reference:
https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701
"""

from __future__ import annotations

import pytest

from running.workout_syntax import (
    SYNTAX_GUIDE_URL,
    assert_description_follows_guide,
    bpm_to_pct_of_max,
    easy_bike_description,
    easy_hr_pct_range,
    easy_run_description,
    extract_step_loads_and_targets,
    format_distance_km,
    format_duration_minutes,
    format_hr_pct_target,
    normalize_workout_description,
    step_line,
)


def test_syntax_guide_url_is_official_forum_doc() -> None:
    """
    Ensure we pin the official Intervals workout-builder guide.

    Returns:
        None: Assertion-only test.
    """
    assert "workout-builder-syntax-quick-guide" in SYNTAX_GUIDE_URL
    assert SYNTAX_GUIDE_URL.startswith("https://forum.intervals.icu/")


def test_bpm_to_pct_matches_athlete_max_hr() -> None:
    """
    Check 80–140 bpm maps to 41–72% at max_hr 195.

    Returns:
        None: Assertion-only test.
    """
    assert bpm_to_pct_of_max(80, 195) == 41
    assert bpm_to_pct_of_max(140, 195) == 72
    assert easy_hr_pct_range() == (41, 72)


def test_format_hr_pct_target_matches_guide_examples() -> None:
    """
    Guide documents forms like ``70% HR`` and ``75-80% HR``.

    Returns:
        None: Assertion-only test.
    """
    assert format_hr_pct_target(70, 70) == "70% HR"
    assert format_hr_pct_target(75, 80) == "75-80% HR"
    assert format_hr_pct_target(41, 72) == "41-72% HR"


def test_easy_run_description_is_guide_compatible() -> None:
    """
    Easy runs must use ``% HR`` (documented), not absolute bpm.

    Absolute bpm is *not* listed in the guide and does not parse on Intervals.

    Returns:
        None: Assertion-only test.
    """
    desc = easy_run_description(12)
    assert desc == "- 12km 41-72% HR (no faster than 4:30 per km)\n"
    assert_description_follows_guide(desc)
    load, target = extract_step_loads_and_targets(desc)[0]
    assert load == "12km"
    assert target == "41-72% HR"
    # Must not emit absolute-bpm targets (not in the guide).
    assert "80-140" not in desc.split("%")[0]
    assert "bpm" not in desc.lower().split("hr")[0]


def test_absolute_bpm_target_rejected_by_step_builder() -> None:
    """
    Refuse absolute bpm targets — they are not in the Intervals guide.

    Returns:
        None: Assertion-only test.
    """
    with pytest.raises(ValueError, match="supported structured target"):
        step_line("12km", "80-140 HR")
    with pytest.raises(ValueError, match="supported structured target"):
        step_line("12km", "80-140bpm HR")


def test_easy_bike_description_uses_zone_hr() -> None:
    """
    Simple bike length uses documented ``Z2 HR`` zone form.

    Returns:
        None: Assertion-only test.
    """
    by_min = easy_bike_description(minutes=90)
    assert by_min == "- 1h30m Z2 HR\n"
    assert_description_follows_guide(by_min)
    by_km = easy_bike_description(km=25)
    assert by_km == "- 25km Z2 HR\n"
    assert_description_follows_guide(by_km)


def test_duration_and_distance_tokens() -> None:
    """
    Duration/distance tokens follow the guide (``m`` = minutes, ``km`` distance).

    Returns:
        None: Assertion-only test.
    """
    assert format_duration_minutes(45) == "45m"
    assert format_duration_minutes(90) == "1h30m"
    assert format_duration_minutes(60) == "1h"
    assert format_distance_km(10) == "10km"
    assert format_distance_km(10.5) == "10.5km"


def test_normalize_bare_zone_on_run() -> None:
    """
    Bare ``Z2`` on Run becomes ``Z2 HR`` for Garmin-safe targets.

    Returns:
        None: Assertion-only test.
    """
    out = normalize_workout_description("- 5km Z2\n", sport="Run")
    assert "Z2 HR" in out


def test_current_week_plan_descriptions_follow_guide() -> None:
    """
    Live week YAML easy/long descriptions must stay guide-compatible.

    Returns:
        None: Assertion-only test.
    """
    from running.week_plan import find_current_week_yaml, load_week_yaml

    week = load_week_yaml(find_current_week_yaml())
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        desc = str(day.get("description") or "").strip()
        if not desc:
            continue
        kind = str(day.get("run_kind") or "").lower()
        if kind in {"easy", "long"} and float(day.get("run_km") or 0) > 0:
            assert_description_follows_guide(desc)
            assert "% HR" in desc
