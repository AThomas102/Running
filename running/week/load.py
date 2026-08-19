"""Load and validate week-plan JSON."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from running.athlete import AthleteAnchors, load_athlete_anchors
from running.schema_io import load as load_json_schema
from running.session import RunSession
from running.week.paths import week_data_root
from running.workout_syntax import as_float

_KM_TOLERANCE = 0.05


def sum_run_km(week: dict[str, Any]) -> float:
    """Sum ``days[].run_km`` for a week plan.

    Args:
        week: Loaded week mapping.

    Returns:
        Total run kilometres.
    """
    total = 0.0
    for day in week.get("days") or []:
        if isinstance(day, dict):
            total += as_float(day.get("run_km"))
    return total


def validate_week_totals(week: dict[str, Any], *, path: Path | None = None) -> None:
    """Require ``run_total_km`` to equal the sum of day run distances.

    Args:
        week: Loaded week mapping.
        path: Optional path for error messages.

    Raises:
        ValueError: If the claimed total does not match the day sum.
    """
    if "run_total_km" not in week:
        raise ValueError(
            f"{path or 'week'}: missing run_total_km — set it to the sum of days[].run_km"
        )
    claimed = as_float(week.get("run_total_km"))
    summed = sum_run_km(week)
    if abs(claimed - summed) > _KM_TOLERANCE:
        where = f"{path}: " if path else ""
        raise ValueError(
            f"{where}run_total_km ({claimed:g}) != sum of days[].run_km ({summed:g}). "
            "Fix the day distances or the total before render/upload."
        )


def day_run_session(day: dict[str, Any]) -> RunSession | None:
    """Parse ``day['run']`` when present.

    Args:
        day: One day mapping.

    Returns:
        A ``RunSession``, or None if ``run`` is absent.

    Raises:
        ValueError: If ``run`` is present but not a mapping.
    """
    raw = day.get("run")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("day.run must be an object")
    return RunSession.from_dict(raw)


def validate_day_sessions(week: dict[str, Any], *, path: Path | None = None) -> None:
    """Require a structured ``run`` when ``run_km`` > 0, and matching distances.

    Args:
        week: Loaded week mapping.
        path: Optional path for error messages.

    Raises:
        ValueError: If a running day is missing ``run``, has a leftover
            ``description``, or ``run_km`` disagrees with session distance.
    """
    where = f"{path}: " if path else ""
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        label = str(day.get("date") or "day")
        if day.get("description"):
            raise ValueError(
                f"{where}{label}: hand-written description is not allowed; "
                "put the workout in day.run (structured session)"
            )
        km = as_float(day.get("run_km"))
        session = day_run_session(day)
        if km > 0 and session is None:
            raise ValueError(
                f"{where}{label}: run_km={km:g} but day.run is missing "
                "(migrate description-only days to a structured run session)"
            )
        if session is None:
            continue
        if session.has_distance_load():
            summed = session.distance_km()
            if abs(summed - km) > _KM_TOLERANCE:
                raise ValueError(
                    f"{where}{label}: run_km ({km:g}) != session distance "
                    f"({summed:g}). Fix day.run blocks or run_km."
                )


def load_week(path: Path, *, root: Path | None = None) -> dict[str, Any]:
    """Load and validate a week plan JSON file.

    Schema-validates against ``schemas/week.schema.json``, then checks
    ``run_total_km`` and session distances. Requires athlete JSON when the
    week names an athlete (for later description rendering).

    Args:
        path: Path to ``YYYY-MM-DD-week.json``.
        root: Optional data/fixture root for athlete JSON.

    Returns:
        Parsed week mapping including ``days``.

    Raises:
        ValueError: If the file fails the schema, totals, or session checks.
        FileNotFoundError: If the athlete JSON sidecar is missing.
    """
    data = load_json_schema(path, "week")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object at the root")
    if not isinstance(data.get("days"), list):
        raise ValueError(f"{path}: days: must be a list")
    validate_week_totals(data, path=path)
    validate_day_sessions(data, path=path)
    athlete = data.get("athlete")
    if athlete:
        load_athlete_anchors(str(athlete), root=week_data_root(path, root=root))
    return data


def load_week_with_anchors(
    path: Path, *, root: Path | None = None
) -> tuple[dict[str, Any], AthleteAnchors]:
    """Load a week JSON and its athlete Pace-band anchors.

    Args:
        path: Path to ``YYYY-MM-DD-week.json``.
        root: Optional data/fixture root.

    Returns:
        ``(week mapping, athlete anchors)``.

    Raises:
        ValueError: If the week has no ``athlete`` field.
        FileNotFoundError: If the athlete JSON sidecar is missing.
    """
    week = load_week(path, root=root)
    athlete = week.get("athlete")
    if not athlete:
        raise ValueError(f"{path}: missing athlete field (needed for Pace bands)")
    anchors = load_athlete_anchors(
        str(athlete), root=week_data_root(path, root=root)
    )
    return week, anchors


def week_start_date(week: dict[str, Any]) -> date:
    """Return the Monday (week start) for a plan.

    Args:
        week: Loaded week mapping.

    Returns:
        Week start date.

    Raises:
        ValueError: If ``week_start`` and day dates are missing.
    """
    raw = week.get("week_start")
    if not raw:
        days = week.get("days") or []
        if days and isinstance(days[0], dict) and days[0].get("date"):
            return date.fromisoformat(str(days[0]["date"])[:10])
        raise ValueError("week_start missing")
    return date.fromisoformat(str(raw)[:10])


def covers_from_week(week: dict[str, Any]) -> tuple[str, str]:
    """Return inclusive ISO date coverage for the week (Mon–Sun).

    Args:
        week: Loaded week mapping.

    Returns:
        ``(oldest, newest)`` as ``YYYY-MM-DD`` strings.
    """
    start = week_start_date(week)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()
