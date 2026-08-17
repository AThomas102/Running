"""Week JSON schema contracts for templates and fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from running.paths import repo_root
from running.schema_io import load, validate
from running.week_plan import load_week, sum_run_km

ROOT = repo_root()
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "weeks"


def test_week_template_matches_schema() -> None:
    """The blank week JSON scaffold must stay schema-valid.

    Purpose:
        Template copy-paste must pass ``schemas/week.schema.json``.
    """
    week = load(ROOT / "templates" / "week.json", "week")
    assert week["run_total_km"] == sum_run_km(week)


def test_valid_fixture_matches_schema() -> None:
    """Offline fixture used by other tests must be a legal week.

    Purpose:
        Other tests load this file; it must pass schema and totals.
    """
    week = load_week(FIXTURES / "valid-week.json")
    assert week["run_total_km"] == 42


def test_mismatched_fixture_fails_arithmetic_not_schema() -> None:
    """Schema allows a totals mismatch; Python arithmetic still refuses it.

    Purpose:
        Totals stay a Python check, not a schema constraint.

    Remove when:
        Totals are expressed in JSON Schema.
    """
    data = load(FIXTURES / "mismatched-total-week.json", "week")
    assert data["run_total_km"] == 99
    with pytest.raises(ValueError, match="run_total_km"):
        load_week(FIXTURES / "mismatched-total-week.json")


def test_validate_rejects_unknown_run_kind() -> None:
    """Reject run_kind values outside the closed enum.

    Purpose:
        ``run_kind`` is ``easy | long | interval | rest``.
    """
    with pytest.raises(ValueError, match="run_kind"):
        validate(
            {
                "week_start": "2026-09-07",
                "run_total_km": 0,
                "days": [
                    {"date": "2026-09-07", "run_km": 0, "run_kind": "sprint"}
                ],
            },
            "week",
        )
