"""Map week-plan days to Intervals calendar upload sessions."""

from __future__ import annotations

from typing import Any

from running.athlete import AthleteAnchors
from running.week.constants import RUN_KINDS_UPLOAD
from running.week.load import day_run_session
from running.workout_syntax import as_float, easy_bike_description


def bike_length(day: dict[str, Any]) -> tuple[str, str] | None:
    """Return planned bike length as ``(unit, display)`` if set.

    Prefer ``bike_min`` over ``bike_km``. No interval structure — simple length only.

    Args:
        day: One day mapping from the week plan.

    Returns:
        ``('min', '90')`` or ``('km', '25')``, else None.
    """
    mins = int(as_float(day.get("bike_min")))
    if mins > 0:
        return "min", str(mins)
    km = as_float(day.get("bike_km"))
    if km > 0:
        return "km", f"{km:g}"
    return None


def bike_session_from_day(day: dict[str, Any]) -> dict[str, Any] | None:
    """Build a Ride upload session when ``bike_min`` or ``bike_km`` is set.

    Args:
        day: One day mapping from the week plan.

    Returns:
        Session dict for Intervals upload, or None.
    """
    length = bike_length(day)
    if length is None:
        return None
    unit, raw = length
    day_date = str(day.get("date") or "")[:10]
    if unit == "min":
        mins = int(raw)
        default_name = f"Easy {mins}min bike"
        default_desc = easy_bike_description(minutes=mins)
    else:
        default_name = f"Easy {raw}km bike"
        default_desc = easy_bike_description(km=float(raw))
    name = day.get("bike_name") or default_name
    desc = day.get("bike_description")
    if desc is None or str(desc).strip() == "":
        desc = default_desc
    return {
        "date": day_date,
        "name": name,
        "type": "Ride",
        "kind": "bike",
        "start_time": str(day.get("bike_start_time") or "10:00"),
        "description": desc,
    }


def sessions_from_week(
    week: dict[str, Any],
    anchors: AthleteAnchors,
) -> list[dict[str, Any]]:
    """Map plan days to Intervals upload sessions (runs + simple bike length).

    Run descriptions are generated from ``day.run`` using athlete Pace bands.

    Args:
        week: Loaded week mapping.
        anchors: Athlete Pace-band anchors.

    Returns:
        Session dicts ready for calendar upsert.
    """
    sessions: list[dict[str, Any]] = []
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        kind = str(day.get("run_kind") or "rest").lower()
        km_f = as_float(day.get("run_km"))
        session = day_run_session(day)
        if kind in RUN_KINDS_UPLOAD and km_f > 0 and session is not None:
            name = (
                day.get("run_name")
                or session.name
                or f"{kind} {km_f:g}k"
            )
            sessions.append(
                {
                    "date": str(day.get("date") or "")[:10],
                    "name": name,
                    "type": "Run",
                    "kind": kind,
                    "start_time": str(day.get("start_time") or "08:00"),
                    "description": session.to_intervals_description(anchors),
                }
            )
        bike = bike_session_from_day(day)
        if bike is not None:
            sessions.append(bike)
    return sessions
