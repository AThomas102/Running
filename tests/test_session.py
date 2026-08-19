"""Tests for structured run sessions (JSON → dataclass → Intervals)."""

from __future__ import annotations

from pathlib import Path

import pytest

from running.athlete import AthleteAnchors, load_athlete_anchors
from running.session import RunSession, Target
from running.workout_syntax import assert_description_follows_guide

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _sample_anchors() -> AthleteAnchors:
    """Load fixture athlete Pace bands."""
    return load_athlete_anchors("athletes/sample.json", root=FIXTURES)


def test_session_from_dict_to_intervals_uses_athlete_band() -> None:
    """Parse JSON and emit a Pace step from the athlete sidecar.

    Purpose:
        ``athlete: easy_pace`` must resolve through athlete JSON.

    Remove when:
        Athlete-band targets are retired.
    """
    session = RunSession.from_dict(
        {
            "kind": "easy",
            "blocks": [{"km": 10, "target": {"athlete": "easy_pace"}}],
        }
    )
    anchors = _sample_anchors()
    desc = session.to_intervals_description(anchors)
    assert desc == f"- 10km {anchors.easy_pace_target()}\n"
    assert session.distance_km() == pytest.approx(10.0)
    assert_description_follows_guide(desc)


def test_session_repeat_and_press_lap_shape() -> None:
    """Render press-lap plus an Nx inner block.

    Purpose:
        Generic interval/stride shape, not one recipe's constants in code.

    Remove when:
        Repeat/press-lap encoding changes.
    """
    session = RunSession.from_dict(
        {
            "blocks": [
                {"km": 5, "target": {"athlete": "easy_pace"}},
                {
                    "press_lap": True,
                    "minutes": 15,
                    "target": {"intensity": "rest"},
                },
                {
                    "reps": 3,
                    "steps": [
                        {"seconds": 20, "target": {"intensity": "active"}},
                        {"seconds": 40, "target": {"intensity": "rest"}},
                    ],
                },
            ]
        }
    )
    desc = session.to_intervals_description(_sample_anchors())
    assert "Press lap 15m intensity=rest" in desc
    assert "3x" in desc
    assert "- 20s intensity=active" in desc
    assert session.has_press_lap()
    assert session.distance_km() == pytest.approx(5.0)
    assert_description_follows_guide(desc)


def test_session_distance_multiplies_repeats() -> None:
    """Count km inside repeats toward session distance.

    Purpose:
        ``run_km`` checks must include repeated distance steps.
    """
    session = RunSession.from_dict(
        {
            "kind": "interval",
            "blocks": [
                {"km": 2, "target": {"hr": "Z2 HR"}},
                {
                    "reps": 4,
                    "steps": [
                        {"km": 0.4, "target": {"pace": "3:40/km Pace"}},
                        {"seconds": 60, "target": {"intensity": "rest"}},
                    ],
                },
            ]
        }
    )
    assert session.distance_km() == pytest.approx(3.6)
    assert session.has_distance_load()


def test_unknown_target_rejected() -> None:
    """Reject a target object with no recognised field.

    Purpose:
        Session parse must not silently drop intensity.
    """
    with pytest.raises(ValueError, match="exactly one field"):
        Target.from_dict({})
    with pytest.raises(ValueError, match="unknown athlete band"):
        Target.from_dict({"athlete": "tempo"})
