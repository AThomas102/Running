"""Load and render weekly plan YAML (single source of truth)."""

from __future__ import annotations

from calendar import month_abbr
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from running.intervals_lib import repo_root

RUN_KINDS_UPLOAD = frozenset({"easy", "long", "interval"})
BIKE_KINDS = frozenset({"commute", "easy"})


def plans_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / "plans"


def find_current_week_yaml(plans: Path | None = None) -> Path:
    d = plans or plans_dir()
    candidates = sorted(d.glob("*-week.yaml"), key=lambda p: p.name)
    # Exclude TEMPLATE.yaml
    candidates = [p for p in candidates if p.name != "TEMPLATE.yaml"]
    if not candidates:
        raise FileNotFoundError(f"No *-week.yaml under {d}")
    return candidates[-1]


def resolve_week_yaml(arg: str | Path | None = None, *, root: Path | None = None) -> Path:
    """Accept path, YYYY-MM-DD, or None (newest week yaml)."""
    d = plans_dir(root)
    if arg is None:
        return find_current_week_yaml(d)
    p = Path(arg)
    if p.suffix == ".yaml" and p.is_file():
        return p
    if p.suffix == ".yaml":
        cand = d / p.name
        if cand.is_file():
            return cand
    text = str(arg).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        cand = d / f"{text}-week.yaml"
        if cand.is_file():
            return cand
        raise FileNotFoundError(f"No week yaml for {text}: {cand}")
    cand = d / text
    if cand.is_file():
        return cand
    raise FileNotFoundError(f"Week yaml not found: {arg}")


def load_week_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at the root")
    if not isinstance(data.get("days"), list):
        raise ValueError(f"{path}: days: must be a list")
    return data


def week_start_date(week: dict[str, Any]) -> date:
    raw = week.get("week_start")
    if not raw:
        days = week.get("days") or []
        if days and isinstance(days[0], dict) and days[0].get("date"):
            return date.fromisoformat(str(days[0]["date"])[:10])
        raise ValueError("week_start missing")
    return date.fromisoformat(str(raw)[:10])


def covers_from_week(week: dict[str, Any]) -> tuple[str, str]:
    start = week_start_date(week)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def format_bike_duration(minutes: int) -> str:
    """Intervals duration token: 90 → 1h30m, 45 → 45m."""
    if minutes <= 0:
        raise ValueError("bike minutes must be positive")
    if minutes >= 60:
        h, m = divmod(minutes, 60)
        return f"{h}h" if m == 0 else f"{h}h{m}m"
    return f"{minutes}m"


def bike_length(day: dict[str, Any]) -> tuple[str, str] | None:
    """Return (unit, display) for a planned easy bike: ('min', '90') or ('km', '25').

    Prefer bike_min over bike_km. No interval structure — simple length only.
    """
    mins = int(_as_float(day.get("bike_min")))
    if mins > 0:
        return "min", str(mins)
    km = _as_float(day.get("bike_km"))
    if km > 0:
        return "km", f"{km:g}"
    return None


def bike_session_from_day(day: dict[str, Any]) -> dict[str, Any] | None:
    """Build a Ride upload session when bike_min or bike_km is set."""
    length = bike_length(day)
    if length is None:
        return None
    unit, raw = length
    day_date = str(day.get("date") or "")[:10]
    if unit == "min":
        mins = int(raw)
        token = format_bike_duration(mins)
        default_name = f"Easy {mins}min bike"
        default_desc = f"- {token} Z2 HR\n"
    else:
        default_name = f"Easy {raw}km bike"
        default_desc = f"- {raw}km Z2 HR\n"
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


def sessions_from_week(week: dict[str, Any]) -> list[dict[str, Any]]:
    """Map plan days to Intervals upload sessions (runs + simple bike length)."""
    sessions: list[dict[str, Any]] = []
    for day in week.get("days") or []:
        if not isinstance(day, dict):
            continue
        kind = str(day.get("run_kind") or "rest").lower()
        km_f = _as_float(day.get("run_km"))
        if kind in RUN_KINDS_UPLOAD and km_f > 0:
            name = day.get("run_name") or f"{kind} {km_f:g}k"
            sessions.append(
                {
                    "date": str(day.get("date") or "")[:10],
                    "name": name,
                    "type": "Run",
                    "kind": kind,
                    "start_time": str(day.get("start_time") or "08:00"),
                    "description": day.get("description")
                    or f"- {km_f:g}km Z2 HR\n",
                }
            )
        bike = bike_session_from_day(day)
        if bike is not None:
            sessions.append(bike)
    return sessions


def _fmt_day_label(d: date, dow: str) -> str:
    return f"**{dow} {d.day}**"


def _run_cell(day: dict[str, Any]) -> str:
    kind = str(day.get("run_kind") or "rest").lower()
    km = day.get("run_km") or 0
    try:
        km_f = float(km)
    except (TypeError, ValueError):
        km_f = 0.0
    if kind == "rest" or km_f <= 0:
        return "**Rest (no run)**" if kind == "rest" else "—"
    label = kind if kind != "easy" else "easy"
    if kind == "long":
        label = "easy"
    if kind == "interval":
        label = "intervals"
    return f"**{km_f:g} km** {label}"


def _bike_also_label(day: dict[str, Any]) -> str | None:
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


def _summary_line(day: dict[str, Any]) -> str:
    dow = str(day.get("dow") or "?")[0]
    # Mon Tue ... use first letter; Thu and Tue both T — use full for Thu as T
    dow_full = str(day.get("dow") or "")
    letter = {"Mon": "M", "Tue": "T", "Wed": "W", "Thu": "T", "Fri": "F", "Sat": "S", "Sun": "S"}.get(
        dow_full, dow_full[:1] or "?"
    )
    kind = str(day.get("run_kind") or "rest").lower()
    km = day.get("run_km") or 0
    try:
        km_f = float(km)
    except (TypeError, ValueError):
        km_f = 0.0
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
    return f"{letter} - {km_f:g}k {kind_word}{sc}{bike_bit}"


def _grid_cell(day: dict[str, Any]) -> str:
    kind = str(day.get("run_kind") or "rest").lower()
    km = day.get("run_km") or 0
    try:
        km_f = float(km)
    except (TypeError, ValueError):
        km_f = 0.0
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
    return f"{km_f:g} {word}{sc}{bike_bit}"


def render_week_markdown(week: dict[str, Any], *, yaml_name: str) -> str:
    start = week_start_date(week)
    end = start + timedelta(days=6)
    title_date = f"{start.day} {month_abbr[start.month]} {start.year}"
    goal = week.get("goal") or ""
    summary_title = week.get("summary_title") or title_date
    run_total = week.get("run_total_km")
    days = [d for d in (week.get("days") or []) if isinstance(d, dict)]

    lines: list[str] = [
        f"<!-- generated from plans/{yaml_name} — edit the YAML -->",
        "",
        f"# Training plan — week of {title_date}",
        "",
        "```yaml",
        f"generated_on: {week.get('generated_on', '')}",
        f"updated_at_gmt: {week.get('updated_at_gmt', '')}",
        f"covers: {start.isoformat()} to {end.isoformat()}",
        f"athlete: {week.get('athlete', '')}",
        f"goal: {goal}",
        "source: " + yaml_name,
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
        and float(d.get("run_km") or 0) > 0
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
    lines.append(key if key else "_See day descriptions in the YAML._")

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


def write_week_markdown(yaml_path: Path, md_path: Path | None = None) -> Path:
    week = load_week_yaml(yaml_path)
    out = md_path or yaml_path.with_suffix(".md")
    out.write_text(
        render_week_markdown(week, yaml_name=yaml_path.name),
        encoding="utf-8",
    )
    return out
