"""Shared helpers for Intervals.icu activity fetch and calendar events."""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from running.workout_syntax import normalize_workout_description

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
API_BASE = "https://intervals.icu/api/v1"


def repo_root() -> Path:
    """
    Return the repository root directory.

    Returns:
        Path: Parent of the ``running/`` package.
    """
    return Path(__file__).resolve().parent.parent


def load_api_key(env_path: Path | None = None) -> str:
    """
    Load ``INTERVALS_API_KEY`` from a ``.env`` file.

    Args:
        env_path (Path | None): Optional path to ``.env``; defaults to repo root.

    Returns:
        str: API key string.

    Raises:
        FileNotFoundError: If the env file is missing.
        KeyError: If the key is not present.
        ValueError: If the key is empty.
    """
    path = env_path or (repo_root() / ".env")
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path}. Create it with: INTERVALS_API_KEY=your_key"
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("INTERVALS_API_KEY="):
            key = line.split("=", 1)[1].strip().strip("'").strip('"')
            if not key:
                raise ValueError("INTERVALS_API_KEY is empty in .env")
            return key
    raise KeyError("INTERVALS_API_KEY not found in .env")


def month_bounds(year_month: str) -> tuple[date, date]:
    """
    Return half-open ``[start, end)`` bounds for a calendar month.

    Args:
        year_month (str): Month as ``YYYY-MM``.

    Returns:
        tuple[date, date]: Inclusive start and exclusive end dates.

    Raises:
        ValueError: If the month string is invalid.
    """
    m = re.fullmatch(r"(\d{4})-(\d{2})", year_month)
    if not m:
        raise ValueError(f"Month must be YYYY-MM, got {year_month!r}")
    year, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {year_month}")
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _auth_header(api_key: str) -> str:
    """
    Build an HTTP Basic Authorization header for Intervals API key auth.

    Args:
        api_key (str): Intervals API key.

    Returns:
        str: ``Basic …`` header value.
    """
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


def request_json(
    method: str,
    path: str,
    api_key: str,
    *,
    params: dict[str, str] | None = None,
    body: Any | None = None,
) -> Any:
    """
    Perform an authenticated JSON HTTP request to Intervals.icu.

    Args:
        method (str): HTTP method (GET, POST, PUT, DELETE, …).
        path (str): API path beginning with ``/``.
        api_key (str): Intervals API key.
        params (dict[str, str] | None): Optional query parameters.
        body (Any | None): Optional JSON-serializable body.

    Returns:
        Any: Parsed JSON response, or None for empty bodies.

    Raises:
        RuntimeError: On HTTP errors.
    """
    url = f"{API_BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {
        "Authorization": _auth_header(api_key),
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            if not raw.strip():
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {err_body}") from e


def get_json(path: str, api_key: str, params: dict[str, str] | None = None) -> Any:
    """
    GET JSON from the Intervals API.

    Args:
        path (str): API path.
        api_key (str): Intervals API key.
        params (dict[str, str] | None): Optional query parameters.

    Returns:
        Any: Parsed JSON response.
    """
    return request_json("GET", path, api_key, params=params)


def post_json(
    path: str,
    api_key: str,
    body: Any,
    *,
    params: dict[str, str] | None = None,
) -> Any:
    """
    POST JSON to the Intervals API.

    Args:
        path (str): API path.
        api_key (str): Intervals API key.
        body (Any): JSON-serializable body.
        params (dict[str, str] | None): Optional query parameters.

    Returns:
        Any: Parsed JSON response.
    """
    return request_json("POST", path, api_key, params=params, body=body)


def put_json(
    path: str,
    api_key: str,
    body: Any,
    *,
    params: dict[str, str] | None = None,
) -> Any:
    """
    PUT JSON to the Intervals API.

    Args:
        path (str): API path.
        api_key (str): Intervals API key.
        body (Any): JSON-serializable body.
        params (dict[str, str] | None): Optional query parameters.

    Returns:
        Any: Parsed JSON response.
    """
    return request_json("PUT", path, api_key, params=params, body=body)


def slugify(text: str) -> str:
    """
    Slugify text for use in external IDs.

    Args:
        text (str): Free-form name.

    Returns:
        str: Lowercase hyphenated slug (or ``session`` if empty).
    """
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "session"


def session_uid(plan_stem: str, session: dict[str, Any]) -> str:
    """
    Build a stable ``external_id`` for a planned session.

    Args:
        plan_stem (str): Week plan filename stem (e.g. ``2026-08-03-week``).
        session (dict[str, Any]): Session mapping with ``date`` and ``name``.

    Returns:
        str: ID such as ``running-repo:…:2026-08-03:easy-12k``.
    """
    day = str(session.get("date") or "")
    name = slugify(str(session.get("name") or "run"))
    return f"running-repo:{plan_stem}:{day}:{name}"


def event_payload_from_session(
    session: dict[str, Any],
    *,
    uid: str,
    default_start_time: str = "08:00",
) -> dict[str, Any]:
    """
    Build an Intervals calendar event payload from a session dict.

    Args:
        session (dict[str, Any]): Session with date, name, type, description.
        uid (str): Stable ``external_id``.
        default_start_time (str): Fallback local start time ``HH:MM``.

    Returns:
        dict[str, Any]: Payload for POST/PUT ``/athlete/0/events``.

    Raises:
        ValueError: If the session has no date.
    """
    day = str(session.get("date") or "").strip()
    if not day:
        raise ValueError(f"session missing date: {session!r}")
    name = str(session.get("name") or "Run").strip()
    sport = str(session.get("type") or "Run").strip()
    start_time = str(session.get("start_time") or default_start_time).strip()
    if len(start_time) == 5:
        start_time = f"{start_time}:00"
    description = session.get("description")
    if description is None:
        description = ""
    description = normalize_workout_description(str(description), sport=sport)
    return {
        "category": "WORKOUT",
        "type": sport,
        "name": name,
        "start_date_local": f"{day}T{start_time}",
        "description": description,
        "external_id": uid,
    }


def list_events(
    api_key: str,
    *,
    oldest: str,
    newest: str,
    category: str = "WORKOUT",
) -> list[dict[str, Any]]:
    """
    List Intervals calendar events in a date range.

    Args:
        api_key (str): Intervals API key.
        oldest (str): Inclusive start ``YYYY-MM-DD``.
        newest (str): Inclusive end ``YYYY-MM-DD``.
        category (str): Event category filter (default ``WORKOUT``).

    Returns:
        list[dict[str, Any]]: Event mappings (empty list if none).
    """
    events = get_json(
        "/athlete/0/events",
        api_key,
        {"oldest": oldest, "newest": newest, "category": category},
    )
    return events if isinstance(events, list) else []


def find_event_by_external_id(
    api_key: str,
    external_id: str,
    *,
    oldest: str,
    newest: str,
) -> dict[str, Any] | None:
    """
    Find a calendar event by ``external_id`` within a date range.

    Args:
        api_key (str): Intervals API key.
        external_id (str): Stable external id to match.
        oldest (str): Inclusive search start ``YYYY-MM-DD``.
        newest (str): Inclusive search end ``YYYY-MM-DD``.

    Returns:
        dict[str, Any] | None: Matching event, or None.
    """
    for ev in list_events(api_key, oldest=oldest, newest=newest):
        if ev.get("external_id") == external_id:
            return ev
    return None


def clear_managed_events(
    api_key: str,
    *,
    oldest: str,
    newest: str,
    prefix: str = "running-repo:",
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    Delete calendar workouts previously pushed by this repo.

    Args:
        api_key (str): Intervals API key.
        oldest (str): Inclusive range start ``YYYY-MM-DD``.
        newest (str): Inclusive range end ``YYYY-MM-DD``.
        prefix (str): ``external_id`` prefix to match (default ``running-repo:``).
        dry_run (bool): If True, collect matches without deleting.

    Returns:
        list[dict[str, Any]]: Events that were (or would be) deleted.
    """
    deleted: list[dict[str, Any]] = []
    for ev in list_events(api_key, oldest=oldest, newest=newest):
        ext = str(ev.get("external_id") or "")
        if not ext.startswith(prefix):
            continue
        deleted.append(ev)
        if dry_run:
            continue
        delete_event(api_key, ev["id"])
    return deleted


def upsert_event(
    api_key: str,
    payload: dict[str, Any],
    *,
    existing_id: int | str | None = None,
) -> Any:
    """
    Create or update a calendar workout, keyed by ``external_id``.

    Intervals assigns its own ``uid``; with API-key auth, stable upserts use
    ``external_id`` plus PUT when an event already exists.

    Args:
        api_key (str): Intervals API key.
        payload (dict[str, Any]): Event body for POST/PUT.
        existing_id (int | str | None): If set, PUT this event id directly.

    Returns:
        Any: API response for the created/updated event.
    """
    if existing_id is not None:
        return put_json(f"/athlete/0/events/{existing_id}", api_key, payload)

    ext = payload.get("external_id")
    start = str(payload.get("start_date_local") or "")[:10]
    if ext and start:
        found = find_event_by_external_id(
            api_key, str(ext), oldest=start, newest=start
        )
        if found and found.get("id") is not None:
            return put_json(f"/athlete/0/events/{found['id']}", api_key, payload)

    return post_json("/athlete/0/events", api_key, payload)


def delete_event(api_key: str, event_id: int | str) -> None:
    """
    Delete a calendar event by id.

    Args:
        api_key (str): Intervals API key.
        event_id (int | str): Intervals event id.

    Returns:
        None: No return value.
    """
    request_json("DELETE", f"/athlete/0/events/{event_id}", api_key)


def garmin_upload_status(api_key: str) -> dict[str, Any]:
    """
    Read Garmin connection / planned-workout upload status from the athlete.

    Args:
        api_key (str): Intervals API key.

    Returns:
        dict[str, Any]: Connection flags and last upload timestamp.
    """
    ath = get_json("/athlete/0", api_key)
    return {
        "training_connected": bool(ath.get("icu_garmin_training")),
        "upload_workouts": bool(ath.get("icu_garmin_upload_workouts")),
        "last_upload": ath.get("icu_garmin_last_upload"),
        "upload_filters": ath.get("icu_garmin_upload_filters"),
    }


def force_garmin_workout_sync(api_key: str) -> dict[str, Any]:
    """
    Force Intervals to re-upload planned workouts to Garmin Connect.

    Intervals has no dedicated sync endpoint. Toggling
    ``icu_garmin_upload_workouts`` off→on triggers a full planned-workout
    re-upload (``icu_garmin_last_upload`` advances).

    Args:
        api_key (str): Intervals API key.

    Returns:
        dict[str, Any]: ``before``/``after`` status and sync ``method``.

    Raises:
        RuntimeError: If Garmin training is not connected.
    """
    before = garmin_upload_status(api_key)
    if not before["training_connected"]:
        raise RuntimeError(
            "Garmin training is not connected in Intervals.icu "
            "(Settings → Connections → Garmin)."
        )
    if not before["upload_workouts"]:
        put_json("/athlete/0", api_key, {"icu_garmin_upload_workouts": True})
        time.sleep(1.5)
        after = garmin_upload_status(api_key)
        return {"before": before, "after": after, "method": "enable"}

    try:
        put_json("/athlete/0", api_key, {"icu_garmin_upload_workouts": False})
        time.sleep(0.75)
        put_json("/athlete/0", api_key, {"icu_garmin_upload_workouts": True})
    except Exception:
        try:
            put_json("/athlete/0", api_key, {"icu_garmin_upload_workouts": True})
        except Exception:
            pass
        raise

    # Background upload job updates last_upload asynchronously.
    after = before
    for _ in range(8):
        time.sleep(0.75)
        after = garmin_upload_status(api_key)
        if after.get("last_upload") != before.get("last_upload"):
            break
    return {"before": before, "after": after, "method": "toggle"}


def nudge_events_for_garmin(
    api_key: str,
    events: list[dict[str, Any]],
) -> int:
    """
    Re-PUT events to re-trigger Garmin export (Intervals dummy-edit trick).

    Args:
        api_key (str): Intervals API key.
        events (list[dict[str, Any]]): Event mappings with ids to nudge.

    Returns:
        int: Number of events re-PUT.
    """
    n = 0
    for ev in events:
        eid = ev.get("id")
        if eid is None:
            continue
        payload = {
            "category": ev.get("category") or "WORKOUT",
            "type": ev.get("type") or "Run",
            "name": ev.get("name"),
            "start_date_local": ev.get("start_date_local"),
            "description": (ev.get("description") or "").rstrip() + "\n",
        }
        if ev.get("external_id"):
            payload["external_id"] = ev["external_id"]
        put_json(f"/athlete/0/events/{eid}", api_key, payload)
        n += 1
    return n


def covers_date_range(meta: dict[str, Any]) -> tuple[str, str] | None:
    """
    Parse frontmatter ``covers: YYYY-MM-DD to YYYY-MM-DD``.

    Args:
        meta (dict[str, Any]): Mapping that may contain ``covers``.

    Returns:
        tuple[str, str] | None: ``(oldest, newest)`` or None if missing/unparsed.
    """
    covers = meta.get("covers")
    if not covers:
        return None
    m = re.search(
        r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
        str(covers),
        re.IGNORECASE,
    )
    if not m:
        return None
    return m.group(1), m.group(2)


def sessions_date_range(sessions: list[dict[str, Any]]) -> tuple[str, str] | None:
    """
    Return min/max session dates.

    Args:
        sessions (list[dict[str, Any]]): Session mappings with ``date`` keys.

    Returns:
        tuple[str, str] | None: ``(oldest, newest)`` or None if empty.
    """
    dates = []
    for s in sessions:
        if isinstance(s, dict) and s.get("date"):
            dates.append(str(s["date"])[:10])
    if not dates:
        return None
    return min(dates), max(dates)


def _parse_start_local(raw: dict[str, Any]) -> str | None:
    """
    Extract a local start timestamp string from an activity payload.

    Args:
        raw (dict[str, Any]): Raw Intervals activity mapping.

    Returns:
        str | None: Local start up to seconds, or None.
    """
    for key in ("start_date_local", "start_date"):
        val = raw.get(key)
        if val:
            return str(val)[:19]  # drop timezone / ms if present
    return None


def _start_date(raw: dict[str, Any]) -> date | None:
    """
    Parse the calendar date of an activity.

    Args:
        raw (dict[str, Any]): Raw Intervals activity mapping.

    Returns:
        date | None: Activity date, or None if missing/invalid.
    """
    s = _parse_start_local(raw)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return date.fromisoformat(s[:10])


def is_run(activity_type: str | None) -> bool:
    """
    Return whether an activity type is a run (not run/bike combo).

    Args:
        activity_type (str | None): Intervals activity type string.

    Returns:
        bool: True if the type looks like a run.
    """
    t = (activity_type or "").lower()
    return "run" in t and "run_bike" not in t


def is_ride(activity_type: str | None) -> bool:
    """
    Return whether an activity type is a bike ride.

    Args:
        activity_type (str | None): Intervals activity type string.

    Returns:
        bool: True if the type looks like a ride.
    """
    t = (activity_type or "").lower()
    return t in {"ride", "virtualride", "cycling", "ebikeride", "gravelride"} or (
        "ride" in t and "run" not in t
    )


def normalize_activity(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a raw Intervals activity into a compact planning dict.

    Args:
        raw (dict[str, Any]): Raw activity from the activities list API.

    Returns:
        dict[str, Any]: Selected fields with distance in km.
    """
    out: dict[str, Any] = {
        "id": raw.get("id"),
        "start_local": _parse_start_local(raw),
        "name": raw.get("name"),
        "type": raw.get("type") or raw.get("sport_type"),
    }
    dist = raw.get("distance")
    if dist is not None:
        out["distance_km"] = round(float(dist) / 1000.0, 3)
    for src, dst in (
        ("moving_time", "moving_time_s"),
        ("elapsed_time", "elapsed_time_s"),
        ("total_elevation_gain", "elevation_m"),
        ("average_heartrate", "average_heartrate"),
        ("max_heartrate", "max_heartrate"),
        ("calories", "calories"),
    ):
        if raw.get(src) is not None:
            out[dst] = raw[src]
    return {k: v for k, v in out.items() if v is not None}


def fetch_month_activities(
    api_key: str,
    year_month: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch activities for one calendar month.

    Args:
        api_key (str): Intervals API key.
        year_month (str): Month as ``YYYY-MM``.
        limit (int): API page size.

    Returns:
        list[dict[str, Any]]: Normalized activities in the month.
    """
    start, end = month_bounds(year_month)
    oldest_param = start.isoformat()
    seen: set[str] = set()
    collected: list[dict[str, Any]] = []

    while True:
        batch = get_json(
            "/athlete/0/activities",
            api_key,
            {"oldest": oldest_param, "limit": str(limit)},
        )
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected response: {batch!r}")
        if not batch:
            break

        new_ids = 0
        batch_dates: list[date] = []
        for raw in batch:
            aid = str(raw.get("id"))
            if aid in seen:
                continue
            seen.add(aid)
            new_ids += 1
            d = _start_date(raw)
            if d is None:
                continue
            batch_dates.append(d)
            if start <= d < end:
                collected.append(normalize_activity(raw))

        if not batch_dates or new_ids == 0:
            break
        latest = max(batch_dates)
        if latest >= end or len(batch) < limit:
            break
        if latest.isoformat() == oldest_param:
            break
        oldest_param = latest.isoformat()
        if len(seen) > 5000:
            break

    collected.sort(key=lambda a: a.get("start_local") or "")
    return collected


def summarize(activities: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Summarize run/ride totals for a list of activities.

    Args:
        activities (list[dict[str, Any]]): Normalized activity mappings.

    Returns:
        dict[str, Any]: Counts and kilometre totals.
    """
    run_km = 0.0
    ride_km = 0.0
    other_km = 0.0
    run_sessions = 0
    longest_run_km = 0.0
    for a in activities:
        km = float(a.get("distance_km") or 0)
        t = a.get("type")
        if is_run(t):
            run_km += km
            run_sessions += 1
            longest_run_km = max(longest_run_km, km)
        elif is_ride(t):
            ride_km += km
        else:
            other_km += km
    return {
        "activity_count": len(activities),
        "run_sessions": run_sessions,
        "run_km": round(run_km, 2),
        "ride_km": round(ride_km, 2),
        "other_km": round(other_km, 2),
        "longest_run_km": round(longest_run_km, 2),
    }


def format_duration(seconds: int | None) -> str:
    """
    Format a duration in seconds as ``H:MM:SS`` or ``M:SS``.

    Args:
        seconds (int | None): Duration in seconds.

    Returns:
        str: Formatted duration, or empty string if None.
    """
    if seconds is None:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def render_month_md(
    year_month: str,
    activities: list[dict[str, Any]],
    summary: dict[str, Any],
    fetched_at_gmt: str,
) -> str:
    """
    Render a monthly activity digest as markdown.

    Args:
        year_month (str): Month as ``YYYY-MM``.
        activities (list[dict[str, Any]]): Normalized activities.
        summary (dict[str, Any]): Output of ``summarize``.
        fetched_at_gmt (str): Fetch timestamp for frontmatter.

    Returns:
        str: Markdown document.
    """
    start, end = month_bounds(year_month)
    lines = [
        "---",
        f"month: {year_month}",
        f"fetched_at_gmt: {fetched_at_gmt}",
        f"activity_count: {summary['activity_count']}",
        f"run_sessions: {summary['run_sessions']}",
        f"run_km: {summary['run_km']}",
        f"ride_km: {summary['ride_km']}",
        f"other_km: {summary['other_km']}",
        f"longest_run_km: {summary['longest_run_km']}",
        "---",
        "",
        f"# Activities — {year_month}",
        "",
        f"Range: {start.isoformat()} → {end.isoformat()} (exclusive end).",
        "",
        "| Date | Type | Name | km | Moving | Avg HR |",
        "|------|------|------|----|--------|--------|",
    ]
    for a in activities:
        day = (a.get("start_local") or "")[:10]
        km = a.get("distance_km", "")
        moving = format_duration(a.get("moving_time_s"))
        hr = a.get("average_heartrate", "")
        name = str(a.get("name") or "").replace("|", "/")
        lines.append(
            f"| {day} | {a.get('type', '')} | {name} | {km} | {moving} | {hr} |"
        )
    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- Run: **{summary['run_km']} km** ({summary['run_sessions']} sessions)",
            f"- Ride: **{summary['ride_km']} km**",
            f"- Other: **{summary['other_km']} km**",
            f"- Longest run: **{summary['longest_run_km']} km**",
            "",
        ]
    )
    return "\n".join(lines)


def gmt_now_iso() -> str:
    """
    Return the current UTC time as an ISO-8601 ``…Z`` string.

    Returns:
        str: Timestamp such as ``2026-08-04T07:00:00Z``.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
