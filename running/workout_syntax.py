"""
Intervals.icu workout description (activity string) builders.

Syntax source of truth:
https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701

Guide pattern for a step:
    - [duration OR distance] [target] [optional cadence]

Heart rate (documented):
    70% HR, 75-80% HR, 95% LTHR, Z2 HR, Z2-Z3 HR

Not documented (and not used as structured targets here):
    absolute bpm ranges such as 80-140 HR / 80-140bpm

Live parse checks (2026-08-03) matched the guide: ``41-72% HR`` becomes
``hr: {start:41, end:72, units:"%hr"}``; absolute bpm does not.
Easy/long defaults now use ``8:00-4:40/km Pace``.
"""

from __future__ import annotations

import re
from typing import Any

# Official Intervals.icu workout-builder syntax guide (forum).
SYNTAX_GUIDE_URL = (
    "https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701"
)

EASY_PACE_FLOOR = "4:40"  # min/km — fastest allowed easy pace
EASY_PACE_CEILING = "8:00"  # min/km — slow end of easy Pace band
# Verified Intervals parse: ``8:00-4:40/km Pace`` → secs/km band.
EASY_PACE_TARGET = f"{EASY_PACE_CEILING}-{EASY_PACE_FLOOR}/km Pace"

# Step line shape from the guide: "- <load> <target> …"
_STEP_LOAD_RE = re.compile(
    r"^(?:"
    r"\d+(?:\.\d+)?km|"  # distance km
    r"\d+(?:\.\d+)?mi|"  # distance mi
    r"\d+mtr|"  # meters (guide: mtr, not m)
    r"\d+h(?:\d+m)?(?:\d+s)?|"  # 1h / 1h30m
    r"\d+m(?:\d+s)?|"  # 10m / 5m30s (minutes)
    r"\d+s"
    r")$"
)
_HR_PCT_TARGET_RE = re.compile(r"^\d+(?:-\d+)?%\s+HR$", re.IGNORECASE)
_HR_ZONE_TARGET_RE = re.compile(r"^Z\d(?:\s*-\s*Z\d)?\s+HR$", re.IGNORECASE)
_PACE_ABS_TARGET_RE = re.compile(
    r"^\d+:\d{2}(?:/\w+)?(?:-\d+:\d{2}(?:/\w+)?)?\s+Pace$", re.IGNORECASE
)
_BARE_ZONE_RE = re.compile(
    r"(?i)(?<![\w%])(Z\d(?:\s*-\s*Z\d)?)(?!\s*(?:HR|Pace|LTHR)\b)"
)
_REPS_LINE_RE = re.compile(r"(?i)^\d+x$|^\w[\w\s]*\s+\d+x$")


def format_hr_pct_target(lo_pct: int, hi_pct: int) -> str:
    """
    Build a guide-documented HR percent target string.

    Args:
        lo_pct: Lower percent of max HR.
        hi_pct: Upper percent of max HR.

    Returns:
        Target such as ``41-72% HR`` (see SYNTAX_GUIDE_URL).
    """
    if lo_pct > hi_pct:
        raise ValueError(f"lo_pct ({lo_pct}) > hi_pct ({hi_pct})")
    if lo_pct == hi_pct:
        return f"{lo_pct}% HR"
    return f"{lo_pct}-{hi_pct}% HR"


def format_distance_km(km: float) -> str:
    """
    Format a distance token for an Intervals step.

    Args:
        km: Distance in kilometres.

    Returns:
        Guide-style distance such as ``12km`` or ``10.5km``.
    """
    if km <= 0:
        raise ValueError(f"km must be positive, got {km}")
    return f"{km:g}km"


def format_duration_minutes(minutes: int) -> str:
    """
    Format a duration token for an Intervals step.

    Args:
        minutes: Duration in whole minutes.

    Returns:
        Guide-style duration such as ``45m`` or ``1h30m``.
    """
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    if minutes >= 60:
        h, m = divmod(minutes, 60)
        return f"{h}h" if m == 0 else f"{h}h{m}m"
    return f"{minutes}m"


def step_line(
    load: str,
    target: str,
    *,
    note: str | None = None,
    trailing_newline: bool = True,
) -> str:
    """
    Build one Intervals workout step line.

    Follows the guide pattern ``- [duration OR distance] [target]``. Optional
    ``note`` is appended in parentheses after the target (free text — not a
    second structured target). Do not put pace tokens like ``4:40/km`` *before*
    the load; the guide treats text before the first duration/distance as cue
    text and it can break parsing.

    Args:
        load: Duration or distance token (e.g. ``12km``, ``1h30m``).
        target: Intensity target (e.g. ``8:00-4:40/km Pace``, ``Z2 HR``).
        note: Optional free-text note after the target.
        trailing_newline: If True, end with a newline (API descriptions).

    Returns:
        Complete step line starting with ``- ``.
    """
    load_s = load.strip()
    target_s = target.strip()
    if not _STEP_LOAD_RE.match(load_s):
        raise ValueError(
            f"load {load_s!r} is not a guide-style duration/distance token "
            f"(see {SYNTAX_GUIDE_URL})"
        )
    if not (
        _HR_PCT_TARGET_RE.match(target_s)
        or _HR_ZONE_TARGET_RE.match(target_s)
        or _PACE_ABS_TARGET_RE.match(target_s)
    ):
        raise ValueError(
            f"target {target_s!r} is not a supported structured target "
            f"(HR % / HR zone / absolute Pace). Guide: {SYNTAX_GUIDE_URL}"
        )
    line = f"- {load_s} {target_s}"
    if note:
        line = f"{line} ({note.strip()})"
    if trailing_newline:
        line += "\n"
    return line


def easy_run_description(
    km: float,
    *,
    pace_ceiling: str = EASY_PACE_CEILING,
    pace_floor: str = EASY_PACE_FLOOR,
) -> str:
    """
    Build the default easy/long run Intervals description.

    Uses absolute ``Pace`` (documented) so Garmin gets a pace band. HR is not
    used: this athlete can run very low HR at fast paces (e.g. ~4:10/km), so
    pace is the easy governor.

    Args:
        km: Run distance in kilometres.
        pace_ceiling: Slow end of easy band as mm:ss per km (e.g. 8:00).
        pace_floor: Fast end of easy band as mm:ss per km (e.g. 4:40).

    Returns:
        Description ending with a newline, e.g.
        ``- 12km 8:00-4:40/km Pace\\n``.
    """
    target = f"{pace_ceiling}-{pace_floor}/km Pace"
    return step_line(format_distance_km(km), target)


def easy_run_with_strides_description(
    km: float,
    *,
    stride_reps: int = 4,
    stride_seconds: int = 20,
    rest_seconds: int = 90,
    bridge_rest_placeholder_minutes: int = 15,
    pace_ceiling: str = EASY_PACE_CEILING,
    pace_floor: str = EASY_PACE_FLOOR,
) -> str:
    """
    Easy km, then an open lap-button rest, then strides with timed rest between reps.

    The bridge uses Intervals ``Press lap`` so Garmin waits until you lap (e.g. while
    relocating). The placeholder minutes are only for load estimate — the step does
    not auto-end on that clock.

    Args:
        km: Easy distance in kilometres.
        stride_reps: Number of stride repetitions.
        stride_seconds: Length of each stride in seconds.
        rest_seconds: Rest/jog between strides in seconds.
        bridge_rest_placeholder_minutes: Nominal minutes for Intervals load
            estimate on the open lap-rest step (does not force end time).
        pace_ceiling: Slow end of easy Pace band (mm:ss per km).
        pace_floor: Fast end of easy Pace band (mm:ss per km).

    Returns:
        Multi-step Intervals description ending with a newline.
    """
    easy = easy_run_description(
        km, pace_ceiling=pace_ceiling, pace_floor=pace_floor
    ).rstrip("\n")
    # Forum syntax: "Press lap <duration> …" — ends on lap (Garmin/Suunto).
    bridge = (
        f"- Press lap {bridge_rest_placeholder_minutes}m intensity=rest"
    )
    reps_header = f"{stride_reps}x"
    stride = f"- {stride_seconds}s intensity=active"
    rest = f"- {rest_seconds}s intensity=rest"
    return f"{easy}\n\n{bridge}\n\n{reps_header}\n{stride}\n{rest}\n"


def easy_bike_description(
    *,
    minutes: int | None = None,
    km: float | None = None,
) -> str:
    """
    Build a simple easy Ride description (length only — no bike intervals).

    Args:
        minutes: Ride duration in minutes (preferred if set).
        km: Ride distance in km if minutes is not set.

    Returns:
        Description with ``Z2 HR`` target (guide-documented zone form).

    Raises:
        ValueError: If neither minutes nor km is a positive length.
    """
    if minutes is not None and minutes > 0:
        return step_line(format_duration_minutes(minutes), "Z2 HR")
    if km is not None and km > 0:
        return step_line(format_distance_km(km), "Z2 HR")
    raise ValueError("easy bike needs positive minutes or km")


def extract_step_loads_and_targets(description: str) -> list[tuple[str, str]]:
    """
    Extract ``(load, target)`` pairs from step lines in a description.

    Args:
        description: Intervals workout description text.

    Returns:
        One pair per ``- …`` step line that matches
        load + structured target.
    """
    out: list[tuple[str, str]] = []
    for raw in description.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        body = line[1:].strip()
        # Drop trailing parenthetical note.
        if " (" in body:
            body = body.split(" (", 1)[0].strip()
        # Open lap-button steps: cue text before duration (Intervals "Press lap …").
        body = re.sub(r"(?i)^press\s+lap\s+", "", body)
        parts = body.split()
        if len(parts) < 2:
            continue
        load = parts[0]
        # Open intensity flags (rest/active/warmup) are valid without Pace/HR.
        if len(parts) >= 2 and parts[1].lower().startswith("intensity="):
            if len(parts) == 2 or (
                len(parts) >= 3
                and parts[2].upper() not in {"HR", "PACE", "LTHR"}
                and not parts[2].endswith("%")
            ):
                # e.g. "- 90s intensity=rest" — not a structured Pace/HR pair
                continue
        # Target may be two tokens: "8:00-4:40/km Pace" or "Z2 HR" or "41-72% HR"
        if len(parts) >= 3 and parts[2].upper() in {"HR", "PACE", "LTHR"}:
            target = f"{parts[1]} {parts[2]}"
        elif len(parts) >= 2 and parts[1].upper() in {"HR", "PACE", "LTHR"}:
            target = parts[1]
        else:
            # e.g. "41-72% HR"
            target = " ".join(parts[1:3]) if len(parts) >= 3 else parts[1]
        out.append((load, target))
    return out


def assert_description_follows_guide(description: str) -> None:
    """
    Raise if step lines do not follow the Intervals syntax guide shapes we use.

    Args:
        description: Workout description to validate.

    Returns:
        Returns None when validation passes.

    Raises:
        AssertionError: If a step load/target is not guide-compatible.
    """
    pairs = extract_step_loads_and_targets(description)
    if not pairs:
        raise AssertionError(
            f"no parseable steps in description {description!r} "
            f"(guide: {SYNTAX_GUIDE_URL})"
        )
    for load, target in pairs:
        if not _STEP_LOAD_RE.match(load):
            raise AssertionError(
                f"load {load!r} not guide-style (guide: {SYNTAX_GUIDE_URL})"
            )
        ok = (
            _HR_PCT_TARGET_RE.match(target)
            or _HR_ZONE_TARGET_RE.match(target)
            or _PACE_ABS_TARGET_RE.match(target)
        )
        if not ok:
            raise AssertionError(
                f"target {target!r} not a documented structured form "
                f"(guide: {SYNTAX_GUIDE_URL})"
            )


def normalize_workout_description(text: str, *, sport: str = "Run") -> str:
    """
    Normalize workout description text before upload.

    Ensures blank lines around repeat headers and, for Run, turns bare ``Z2``
    into ``Z2 HR`` so Garmin gets an explicit HR zone target.

    Args:
        text: Raw Intervals description.
        sport: Activity type (e.g. ``Run``, ``Ride``).

    Returns:
        Normalized description ending with a newline.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    is_run = "run" in sport.lower()

    for line in lines:
        stripped = line.strip()
        is_reps = bool(_REPS_LINE_RE.match(stripped))
        if is_reps and out and out[-1].strip():
            out.append("")

        if (
            is_run
            and stripped.startswith("-")
            and re.search(r"(?i)\b(?:HR|Pace|LTHR|%|/\w+)\b", stripped) is None
        ):
            line = _BARE_ZONE_RE.sub(r"\1 HR", line)

        out.append(line.rstrip())

    cleaned: list[str] = []
    blank_run = 0
    for line in out:
        if not line.strip():
            blank_run += 1
            if blank_run <= 1:
                cleaned.append("")
        else:
            blank_run = 0
            cleaned.append(line)
    return "\n".join(cleaned).strip() + "\n"


def as_float(value: Any, default: float = 0.0) -> float:
    """
    Coerce a value to float with a fallback.

    Args:
        value: Value to convert.
        default: Value returned if conversion fails.

    Returns:
        Converted number or default.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
