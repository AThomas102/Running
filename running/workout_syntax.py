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
"""

from __future__ import annotations

import re
from typing import Any

# Official Intervals.icu workout-builder syntax guide (forum).
SYNTAX_GUIDE_URL = (
    "https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701"
)

# Athlete easy-run BPM band and Intervals Run max_hr used to map to % HR.
EASY_HR_BPM_MIN = 80
EASY_HR_BPM_MAX = 140
DEFAULT_RUN_MAX_HR = 195
EASY_PACE_FLOOR = "4:30"  # min/km; slower OK — note text only, not a Pace target

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


def bpm_to_pct_of_max(bpm: int, max_hr: int) -> int:
    """
    Convert absolute heart rate to percent of max HR (rounded).

    Args:
        bpm (int): Absolute heart rate in beats per minute.
        max_hr (int): Athlete maximum heart rate.

    Returns:
        int: Percent of max HR (0–100 scale integer).

    Raises:
        ValueError: If max_hr is not positive or bpm is negative.
    """
    if max_hr <= 0:
        raise ValueError(f"max_hr must be positive, got {max_hr}")
    if bpm < 0:
        raise ValueError(f"bpm must be >= 0, got {bpm}")
    return int(round(100.0 * bpm / max_hr))


def easy_hr_pct_range(
    *,
    bpm_min: int = EASY_HR_BPM_MIN,
    bpm_max: int = EASY_HR_BPM_MAX,
    max_hr: int = DEFAULT_RUN_MAX_HR,
) -> tuple[int, int]:
    """
    Map easy BPM band to an Intervals ``% HR`` range.

    Args:
        bpm_min (int): Lower easy HR in bpm.
        bpm_max (int): Upper easy HR in bpm.
        max_hr (int): Athlete max HR used for the percent conversion.

    Returns:
        tuple[int, int]: Inclusive (lo_pct, hi_pct) for use as ``lo-hi% HR``.
    """
    if bpm_min > bpm_max:
        raise ValueError(f"bpm_min ({bpm_min}) > bpm_max ({bpm_max})")
    return bpm_to_pct_of_max(bpm_min, max_hr), bpm_to_pct_of_max(bpm_max, max_hr)


def format_hr_pct_target(lo_pct: int, hi_pct: int) -> str:
    """
    Build a guide-documented HR percent target string.

    Args:
        lo_pct (int): Lower percent of max HR.
        hi_pct (int): Upper percent of max HR.

    Returns:
        str: Target such as ``41-72% HR`` (see SYNTAX_GUIDE_URL).
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
        km (float): Distance in kilometres.

    Returns:
        str: Guide-style distance such as ``12km`` or ``10.5km``.
    """
    if km <= 0:
        raise ValueError(f"km must be positive, got {km}")
    return f"{km:g}km"


def format_duration_minutes(minutes: int) -> str:
    """
    Format a duration token for an Intervals step.

    Args:
        minutes (int): Duration in whole minutes.

    Returns:
        str: Guide-style duration such as ``45m`` or ``1h30m``.
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
    second structured target). Do not put pace tokens like ``4:30/km`` *before*
    the load; the guide treats text before the first duration/distance as cue
    text and it can break parsing.

    Args:
        load (str): Duration or distance token (e.g. ``12km``, ``1h30m``).
        target (str): Intensity target (e.g. ``41-72% HR``, ``Z2 HR``).
        note (str | None): Optional free-text note after the target.
        trailing_newline (bool): If True, end with a newline (API descriptions).

    Returns:
        str: Complete step line starting with ``- ``.
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
    bpm_min: int = EASY_HR_BPM_MIN,
    bpm_max: int = EASY_HR_BPM_MAX,
    max_hr: int = DEFAULT_RUN_MAX_HR,
    pace_floor: str = EASY_PACE_FLOOR,
) -> str:
    """
    Build the default easy/long run Intervals description.

    Uses ``% HR`` (documented) so Intervals can parse a structured HR range for
    Garmin. Absolute bpm is not in the guide and is not used as the target.

    Args:
        km (float): Run distance in kilometres.
        bpm_min (int): Easy lower HR in bpm (mapped to % of max_hr).
        bpm_max (int): Easy upper HR in bpm (mapped to % of max_hr).
        max_hr (int): Athlete max HR for the percent conversion.
        pace_floor (str): Slowest allowed pace as mm:ss per km (note text only).

    Returns:
        str: Description ending with a newline, e.g.
        ``- 12km 41-72% HR (no faster than 4:30 per km)\\n``.
    """
    lo, hi = easy_hr_pct_range(bpm_min=bpm_min, bpm_max=bpm_max, max_hr=max_hr)
    return step_line(
        format_distance_km(km),
        format_hr_pct_target(lo, hi),
        note=f"no faster than {pace_floor} per km",
    )


def easy_bike_description(
    *,
    minutes: int | None = None,
    km: float | None = None,
) -> str:
    """
    Build a simple easy Ride description (length only — no bike intervals).

    Args:
        minutes (int | None): Ride duration in minutes (preferred if set).
        km (float | None): Ride distance in km if minutes is not set.

    Returns:
        str: Description with ``Z2 HR`` target (guide-documented zone form).

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
        description (str): Intervals workout description text.

    Returns:
        list[tuple[str, str]]: One pair per ``- …`` step line that matches
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
        parts = body.split()
        if len(parts) < 2:
            continue
        load = parts[0]
        # Target may be two tokens: "41-72% HR" or "Z2 HR" or "8:00-4:30/km Pace"
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
        description (str): Workout description to validate.

    Returns:
        None: Returns None when validation passes.

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
        text (str): Raw Intervals description.
        sport (str): Activity type (e.g. ``Run``, ``Ride``).

    Returns:
        str: Normalized description ending with a newline.
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
        value (Any): Value to convert.
        default (float): Value returned if conversion fails.

    Returns:
        float: Converted number or default.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
