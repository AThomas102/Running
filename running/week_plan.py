"""Load and render weekly plan JSON (single source of truth)."""

from __future__ import annotations

from calendar import month_abbr
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from running.paths import data_root
from running.schema_io import load as load_json_schema
from running.workout_syntax import (
    as_float,
    easy_bike_description,
    easy_run_description,
    format_duration_minutes,
)

RUN_KINDS_UPLOAD = frozenset({"easy", "long", "interval"})
BIKE_KINDS = frozenset({"commute", "easy"})


def plans_dir(root: Path | None = None) -> Path:
    """Return the live plans directory under the personal-data root.

    Args:
        root: Optional repo/fixture root. When set, use ``root/plans``
            (tests). When omitted, use ``data_root()/plans``.

    Returns:
        Path to the ``plans/`` directory.
    """
    return data_root(root) / "plans"


def find_current_week_json(plans: Path | None = None) -> Path:
    """Find the newest ``*-week.json`` by Monday date in the filename.

    Args:
        plans: Plans directory; defaults to ``plans_dir()``.

    Returns:
        Path to the current week JSON.

    Raises:
        FileNotFoundError: If no week JSON files exist.
    """
    d = plans or plans_dir()
    candidates = sorted(d.glob("*-week.json"), key=lambda p: p.name)
    candidates = [p for p in candidates if p.name != "week.json"]
    if not candidates:
        raise FileNotFoundError(f"No *-week.json under {d}")
    return candidates[-1]


def resolve_week_json(arg: str | Path | None = None, *, root: Path | None = None) -> Path:
    """Resolve a week JSON from a path, Monday date, or newest file.

    Args:
        arg: Path, ``YYYY-MM-DD``, or None for newest.
        root: Optional repo/fixture root for ``plans_dir``.

    Returns:
        Resolved week JSON path.

    Raises:
        FileNotFoundError: If the requested week file does not exist.
    """
    d = plans_dir(root)
    if arg is None:
        return find_current_week_json(d)
    p = Path(arg)
    if p.suffix == ".json" and p.is_file():
        return p
    if p.suffix == ".json":
        cand = d / p.name
        if cand.is_file():
            return cand
    text = str(arg).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        cand = d / f"{text}-week.json"
        if cand.is_file():
            return cand
        raise FileNotFoundError(f"No week json for {text}: {cand}")
    cand = d / text
    if cand.is_file():
        return cand
    raise FileNotFoundError(f"Week json not found: {arg}")


def sum_run_km(week: dict[str, Any]) -> float:
    """
    Sum ``days[].run_km`` for a week plan.

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
    """
    Require ``run_total_km`` to equal the sum of day run distances.

    Args:
        week: Loaded week mapping.
        path: Optional path for error messages.

    Returns:
        Returns None when validation passes.

    Raises:
        ValueError: If the claimed total does not match the day sum.
    """
    if "run_total_km" not in week:
        raise ValueError(
            f"{path or 'week'}: missing run_total_km — set it to the sum of days[].run_km"
        )
    claimed = as_float(week.get("run_total_km"))
    summed = sum_run_km(week)
    if abs(claimed - summed) > 0.05:
        where = f"{path}: " if path else ""
        raise ValueError(
            f"{where}run_total_km ({claimed:g}) != sum of days[].run_km ({summed:g}). "
            "Fix the day distances or the total before render/upload."
        )


def load_week(path: Path) -> dict[str, Any]:
    """Load and validate a week plan JSON file.

    Schema-validates against ``schemas/week.schema.json``, then checks
    ``run_total_km`` against the day sum.

    Args:
        path: Path to ``YYYY-MM-DD-week.json``.

    Returns:
        Parsed week mapping including ``days``.

    Raises:
        ValueError: If the file fails the schema or totals mismatch.
    """
    data = load_json_schema(path, "week")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object at the root")
    if not isinstance(data.get("days"), list):
        raise ValueError(f"{path}: days: must be a list")
    validate_week_totals(data, path=path)
    return data


def week_start_date(week: dict[str, Any]) -> date:
    """
    Return the Monday (week start) for a plan.

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
    """
    Return inclusive ISO date coverage for the week (Mon–Sun).

    Args:
        week: Loaded week mapping.

    Returns:
        ``(oldest, newest)`` as ``YYYY-MM-DD`` strings.
    """
    start = week_start_date(week)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def format_bike_duration(minutes: int) -> str:
    """
    Format bike duration for Intervals step syntax.

    Args:
        minutes: Duration in minutes.

    Returns:
        Token such as ``90m`` or ``1h30m``.
    """
    return format_duration_minutes(minutes)


def bike_length(day: dict[str, Any]) -> tuple[str, str] | None:
    """
    Return planned bike length as ``(unit, display)`` if set.

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
    """
    Build a Ride upload session when ``bike_min`` or ``bike_km`` is set.

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


def default_easy_run_description(km: float) -> str:
    """
    Build the default easy/long run Intervals description.

    Args:
        km: Run distance in kilometres.

    Returns:
        Guide-compatible step with absolute ``Pace`` band (4:40–8:00/km).
    """
    return easy_run_description(km)


def sessions_from_week(week: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Map plan days to Intervals upload sessions (runs + simple bike length).

    Args:
        week: Loaded week mapping.

    Returns:
        Session dicts ready for calendar upsert.
    """
    sessions: list[dict[str, Any]] = []
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        kind = str(day.get("run_kind") or "rest").lower()
        km_f = as_float(day.get("run_km"))
        if kind in RUN_KINDS_UPLOAD and km_f > 0:
            name = day.get("run_name") or f"{kind} {km_f:g}k"
            desc = day.get("description")
            if desc is None or str(desc).strip() == "":
                if kind in {"easy", "long"}:
                    desc = default_easy_run_description(km_f)
                else:
                    desc = f"- {km_f:g}km Z2 HR\n"
            sessions.append(
                {
                    "date": str(day.get("date") or "")[:10],
                    "name": name,
                    "type": "Run",
                    "kind": kind,
                    "start_time": str(day.get("start_time") or "08:00"),
                    "description": desc,
                }
            )
        bike = bike_session_from_day(day)
        if bike is not None:
            sessions.append(bike)
    return sessions


def _fmt_day_label(d: date, dow: str) -> str:
    """
    Format a schedule-table day label.

    Args:
        d: Calendar date.
        dow: Weekday abbreviation (e.g. ``Mon``).

    Returns:
        Markdown-bold label such as ``**Mon 3**``.
    """
    return f"**{dow} {d.day}**"


def _run_cell(day: dict[str, Any]) -> str:
    """
    Format the Run column cell for one day.

    Args:
        day: Day mapping.

    Returns:
        Markdown cell contents.
    """
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
    """
    Format bike-related text for the Also column.

    Args:
        day: Day mapping.

    Returns:
        Label, or None if no bike note.
    """
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
    """
    Format the Also column cell for one day.

    Args:
        day: Day mapping.

    Returns:
        Markdown cell contents.
    """
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
    """Return True if the day's name or description mentions strides.

    Args:
        day: Day mapping.

    Returns:
        True when ``stride`` appears in ``run_name`` or ``description``.
    """
    blob = f"{day.get('run_name', '')}\n{day.get('description', '')}".lower()
    return "stride" in blob


def _summary_line(day: dict[str, Any]) -> str:
    """
    Format one copy-paste summary line for a day.

    Args:
        day: Day mapping.

    Returns:
        Summary line such as ``M - 12k easy + S&C``.
    """
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
    """
    Format one cell in the compact week grid.

    Args:
        day: Day mapping.

    Returns:
        Compact grid text.
    """
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


def render_week_markdown(week: dict[str, Any], *, source_name: str) -> str:
    """Render a week mapping to readable markdown.

    Args:
        week: Loaded week mapping.
        source_name: Source filename for the generated header comment.

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

    lines.extend(["", "## Key sessions", ""])
    key = str(week.get("key_sessions") or "").strip()
    lines.append(key if key else "_See day descriptions in the JSON._")

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


def write_week_markdown(json_path: Path, md_path: Path | None = None) -> Path:
    """Render a week JSON file to its markdown companion.

    Args:
        json_path: Source ``*-week.json``.
        md_path: Optional output path; defaults to ``.md`` sibling.

    Returns:
        Path written.
    """
    week = load_week(json_path)
    out = md_path or json_path.with_suffix(".md")
    out.write_text(
        render_week_markdown(week, source_name=json_path.name),
        encoding="utf-8",
    )
    return out
