"""Render week-plan JSON to readable markdown."""

from __future__ import annotations

from calendar import month_abbr
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from running.athlete import AthleteAnchors
from running.week.constants import BIKE_KINDS, RUN_KINDS_UPLOAD
from running.week.load import (
    day_run_session,
    load_week_with_anchors,
    week_start_date,
)
from running.week.sessions import bike_length
from running.workout_syntax import as_float


def _fmt_day_label(d: date, dow: str) -> str:
    """Format a schedule-table day label.

    Args:
        d: Calendar date.
        dow: Weekday abbreviation (e.g. ``Mon``).

    Returns:
        Markdown-bold label such as ``**Mon 3**``.
    """
    return f"**{dow} {d.day}**"


def _run_cell(day: dict[str, Any]) -> str:
    """Format the Run column cell for one day."""
    kind = str(day.get("run_kind") or "rest").lower()
    km_f = as_float(day.get("run_km"))
    if kind == "rest" or km_f <= 0:
        return "**Rest (no run)**" if kind == "rest" else "—"
    label = kind if kind != "easy" else "easy"
    if kind == "long":
        label = "easy"
    if kind == "interval":
        label = "intervals"
    return f"**{km_f:g} km** {label}"


def _bike_also_label(day: dict[str, Any]) -> str | None:
    """Format bike-related text for the Also column."""
    length = bike_length(day)
    if length is not None:
        unit, raw = length
        if unit == "min":
            return f"**{raw} min** easy bike"
        return f"**{raw} km** easy bike"
    bike = str(day.get("bike") or "none").lower()
    if bike == "commute":
        return "Commute bike OK"
    if bike == "easy":
        return "Easy bike OK"
    return None


def _also_cell(day: dict[str, Any]) -> str:
    """Format the Also column cell for one day."""
    parts: list[str] = []
    if day.get("sc"):
        parts.append("S&C")
    bike_label = _bike_also_label(day)
    if bike_label:
        parts.append(bike_label)
    note = str(day.get("note") or "").strip()
    kind = str(day.get("run_kind") or "").lower()
    if kind == "rest" and note and not parts:
        return note
    if not parts:
        return note if note else "—"
    if note and kind != "rest":
        parts.append(note)
    return "; ".join(parts)


def _has_strides(day: dict[str, Any]) -> bool:
    """Return True if the day's name or session looks like a stride workout."""
    session = day_run_session(day)
    blob = f"{day.get('run_name', '')}\n{session.name if session else ''}".lower()
    if "stride" in blob:
        return True
    return bool(session and session.has_press_lap())


def _summary_line(day: dict[str, Any]) -> str:
    """Format one copy-paste summary line for a day."""
    dow_full = str(day.get("dow") or "")
    letter = {
        "Mon": "M",
        "Tue": "T",
        "Wed": "W",
        "Thu": "T",
        "Fri": "F",
        "Sat": "S",
        "Sun": "S",
    }.get(dow_full, dow_full[:1] or "?")
    kind = str(day.get("run_kind") or "rest").lower()
    km_f = as_float(day.get("run_km"))
    sc = " + S&C" if day.get("sc") else ""
    length = bike_length(day)
    bike_bit = ""
    if length is not None:
        unit, raw = length
        bike_bit = f" + {raw}min bike" if unit == "min" else f" + {raw}km bike"
    if kind == "rest" or km_f <= 0:
        note = str(day.get("note") or "").strip()
        if length is not None:
            unit, raw = length
            label = f"{raw}min easy bike" if unit == "min" else f"{raw}km easy bike"
            return f"{letter} - Rest + {label}"
        if note:
            return f"{letter} - {note}"
        bike = str(day.get("bike") or "none").lower()
        if bike == "commute":
            return f"{letter} - Rest (+ easy commute bike OK)"
        if bike == "easy":
            return f"{letter} - Rest (+ easy bike OK)"
        return f"{letter} - Rest"
    kind_word = "easy"
    if kind == "long":
        kind_word = "easy"
    elif kind == "interval":
        kind_word = "intervals"
    strides = " + strides" if _has_strides(day) else ""
    return f"{letter} - {km_f:g}k {kind_word}{strides}{sc}{bike_bit}"


def _grid_cell(day: dict[str, Any]) -> str:
    """Format one cell in the compact week grid."""
    kind = str(day.get("run_kind") or "rest").lower()
    km_f = as_float(day.get("run_km"))
    sc = " + S&C" if day.get("sc") else ""
    length = bike_length(day)
    bike_bit = ""
    if length is not None:
        unit, raw = length
        bike_bit = f" +{raw}m bike" if unit == "min" else f" +{raw}k bike"
    bike = str(day.get("bike") or "none").lower()
    if kind == "rest" or km_f <= 0:
        if length is not None:
            return f"Rest{bike_bit}"
        if bike in BIKE_KINDS:
            return "Rest (+ bike)"
        return "Rest"
    word = "easy"
    if kind == "interval":
        word = "intervals"
    elif kind == "long":
        word = "easy"
    strides = " + strides" if _has_strides(day) else ""
    return f"{km_f:g} {word}{strides}{sc}{bike_bit}"


def _workouts_section(days: list[dict[str, Any]], anchors: AthleteAnchors) -> list[str]:
    """Build the Workouts markdown section from generated Intervals text."""
    lines = ["## Workouts", ""]
    any_run = False
    for day in days:
        session = day_run_session(day)
        if session is None:
            continue
        any_run = True
        d = date.fromisoformat(str(day.get("date"))[:10])
        dow = str(day.get("dow") or d.strftime("%a"))
        name = day.get("run_name") or session.name or "Run"
        lines.append(f"### {dow} {d.day} — {name}")
        lines.append("")
        lines.append("```")
        lines.append(session.to_intervals_description(anchors).rstrip("\n"))
        lines.append("```")
        lines.append("")
    if not any_run:
        lines.append("_No run sessions._")
        lines.append("")
    return lines


def render_week_markdown(
    week: dict[str, Any],
    *,
    source_name: str,
    anchors: AthleteAnchors,
) -> str:
    """Render a week mapping to readable markdown.

    Args:
        week: Loaded week mapping.
        source_name: Source filename for the generated header comment.
        anchors: Athlete Pace bands for workout descriptions.

    Returns:
        Full markdown document.
    """
    start = week_start_date(week)
    end = start + timedelta(days=6)
    title_date = f"{start.day} {month_abbr[start.month]} {start.year}"
    goal = week.get("goal") or ""
    summary_title = week.get("summary_title") or title_date
    run_total = week.get("run_total_km")
    days = [d for d in (week.get("days") or []) if isinstance(d, dict)]

    lines: list[str] = [
        f"<!-- generated from plans/{source_name} — edit the JSON -->",
        "",
        f"# Training plan — week of {title_date}",
        "",
        "```yaml",
        f"generated_on: {week.get('generated_on', '')}",
        f"updated_at_gmt: {week.get('updated_at_gmt', '')}",
        f"covers: {start.isoformat()} to {end.isoformat()}",
        f"athlete: {week.get('athlete', '')}",
        f"goal: {goal}",
        "source: " + source_name,
        "```",
        "",
        "## Summary (copy-paste)",
        "",
        "```",
        f"Running Plan {summary_title}",
    ]
    for day in days:
        lines.append(_summary_line(day))
    if run_total is not None:
        lines.append(f"(~{run_total} km run)")
    lines.extend(["```", "", "## Context", ""])
    ctx = str(week.get("context") or "").strip()
    lines.append(ctx if ctx else "_No context._")
    lines.extend(["", "## Watch-fors", ""])
    watch = week.get("watch_fors") or []
    if isinstance(watch, list) and watch:
        for w in watch:
            lines.append(f"- {w}")
    else:
        lines.append("- _None listed._")

    lines.extend(["", "## Schedule", ""])
    n_run_days = sum(
        1
        for d in days
        if str(d.get("run_kind") or "").lower() in RUN_KINDS_UPLOAD
        and as_float(d.get("run_km")) > 0
    )
    total_bit = f"**Run total ≈ {run_total} km**" if run_total is not None else "**Run days**"
    lines.append(f"{total_bit} ({n_run_days} days).")
    lines.append("")
    lines.append("| Day | Run | Also |")
    lines.append("|-----|-----|------|")
    for day in days:
        d = date.fromisoformat(str(day.get("date"))[:10])
        dow = str(day.get("dow") or d.strftime("%a"))
        lines.append(
            f"| {_fmt_day_label(d, dow)} | {_run_cell(day)} | {_also_cell(day)} |"
        )

    lines.append("")
    lines.append(
        "| Week starting | Mon | Tue | Wed | Thu | Fri | Sat | Sun | Total (km) |"
    )
    lines.append(
        "|---------------|-----|-----|-----|-----|-----|-----|-----|------------|"
    )
    by_dow = {str(d.get("dow")): d for d in days}
    grid = [
        _grid_cell(by_dow[k]) if k in by_dow else ""
        for k in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    ]
    total_cell = f"**~{run_total}**" if run_total is not None else ""
    lines.append(
        f"| {start.isoformat()} | "
        + " | ".join(grid)
        + f" | {total_cell} |"
    )

    lines.append("")
    lines.extend(_workouts_section(days, anchors))

    lines.extend(["## Key sessions", ""])
    key = str(week.get("key_sessions") or "").strip()
    lines.append(key if key else "_See Workouts above._")

    lines.extend(["", "## Strength and recovery", ""])
    strength = str(week.get("strength_and_recovery") or "").strip()
    lines.append(strength if strength else "_None listed._")

    lines.extend(["", "## Path after this week", ""])
    path = str(week.get("path_after") or "").strip()
    lines.append(path if path else "_TBD._")

    lines.extend(["", "## Evaluation notes", ""])
    ev = str(week.get("evaluation_notes") or "").strip()
    lines.append(ev if ev else "_TBD._")
    lines.append("")
    return "\n".join(lines)


def write_week_markdown(
    json_path: Path,
    md_path: Path | None = None,
    *,
    root: Path | None = None,
) -> Path:
    """Render a week JSON file to its markdown companion.

    Args:
        json_path: Source ``*-week.json``.
        md_path: Optional output path; defaults to ``.md`` sibling.
        root: Optional data/fixture root for athlete JSON.

    Returns:
        Path written.
    """
    week, anchors = load_week_with_anchors(json_path, root=root)
    out = md_path or json_path.with_suffix(".md")
    out.write_text(
        render_week_markdown(week, source_name=json_path.name, anchors=anchors),
        encoding="utf-8",
    )
    return out
