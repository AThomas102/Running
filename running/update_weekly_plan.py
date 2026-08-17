"""Upsert weekly plan sessions onto the Intervals.icu calendar."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from running.intervals_lib import (
    clear_managed_events,
    covers_date_range,
    event_payload_from_session,
    force_garmin_workout_sync,
    garmin_upload_status,
    list_events,
    load_api_key,
    nudge_events_for_garmin,
    repo_root,
    session_uid,
    sessions_date_range,
    upsert_event,
)
from running.week_plan import covers_from_week, load_week, resolve_week_json, sessions_from_week

# HR zones + intensity flags → structured steps Garmin can execute.
# Bare "Z2" alone is treated as power and will not guide a run watch correctly.
DEMO_DESCRIPTION = """\
Warmup
- 2km intensity=warmup Z2 HR

5x
- 1km intensity=active Z4 HR
- 90s intensity=rest Z1 HR

Cooldown
- 1km intensity=cooldown Z2 HR
"""


def refuse_past_plan(
    meta: dict,
    sessions: list[dict],
    *,
    today: date,
) -> None:
    """
    Hard-error if the plan's covered range / all sessions are before today.

    Args:
        meta: Week mapping (or legacy frontmatter).
        sessions: Upload session dicts.
        today: Local "today" for past-day protection.

    Returns:
        Returns None when the plan may be uploaded.

    Raises:
        SystemExit: If the plan is entirely in the past.
    """
    covers = None
    if meta.get("week_start") or meta.get("days"):
        try:
            covers = covers_from_week(meta)
        except ValueError:
            covers = None
    if covers is None:
        covers = covers_date_range(meta)
    if covers:
        end = date.fromisoformat(covers[1])
        if end < today:
            raise SystemExit(
                f"Refusing upload: plan covers {covers[0]} to {covers[1]}, "
                f"which ends before today ({today.isoformat()}). "
                "Past weeks are not uploaded."
            )
    rng = sessions_date_range(sessions)
    if rng:
        end = date.fromisoformat(rng[1])
        if end < today:
            raise SystemExit(
                f"Refusing upload: all sessions are on/before {rng[1]}, "
                f"before today ({today.isoformat()}). "
                "Past days are never updated."
            )


def session_date(session: dict) -> date:
    """
    Parse a session date field to a ``date``.

    Args:
        session: Session mapping with a ``date`` key.

    Returns:
        Session calendar date.

    Raises:
        SystemExit: If the date is missing or invalid.
    """
    raw = session.get("date")
    if not raw:
        raise SystemExit(f"Session missing date: {session!r}")
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as e:
        raise SystemExit(f"Invalid session date {raw!r}: {e}") from e


def clamp_clear_range(
    oldest: str,
    newest: str,
    *,
    today: date,
) -> tuple[str, str] | None:
    """
    Clear only from today onward; never delete past calendar days.

    Args:
        oldest: Inclusive range start ``YYYY-MM-DD``.
        newest: Inclusive range end ``YYYY-MM-DD``.
        today: Local today.

    Returns:
        Clamped ``(oldest, newest)``, or None if all past.
    """
    start = date.fromisoformat(oldest)
    end = date.fromisoformat(newest)
    if end < today:
        return None
    if start < today:
        start = today
    if start > end:
        return None
    return start.isoformat(), end.isoformat()


def partition_sessions(
    sessions: list[dict],
    *,
    today: date,
) -> tuple[list[dict], list[dict]]:
    """
    Split sessions into past vs today-or-future.

    Args:
        sessions: Session mappings.
        today: Local today.

    Returns:
        ``(past_sessions, today_or_future)``.
    """
    past: list[dict] = []
    future: list[dict] = []
    for s in sessions:
        if session_date(s) < today:
            past.append(s)
        else:
            future.append(s)
    return past, future


def clear_range(
    api_key: str,
    oldest: str,
    newest: str,
    *,
    dry_run: bool,
) -> None:
    """
    Clear managed ``running-repo:`` calendar events in a date range.

    Args:
        api_key: Intervals API key.
        oldest: Inclusive range start ``YYYY-MM-DD``.
        newest: Inclusive range end ``YYYY-MM-DD``.
        dry_run: If True, print only and do not delete.

    Returns:
        Prints a summary of cleared events.
    """
    if dry_run:
        print(f"  would clear managed event(s) in {oldest}..{newest}")
        return
    removed = clear_managed_events(
        api_key, oldest=oldest, newest=newest, dry_run=False
    )
    print(f"  cleared {len(removed)} managed event(s) in {oldest}..{newest}")
    for ev in removed:
        print(
            f"    - {str(ev.get('start_date_local') or '')[:10]}  "
            f"{ev.get('name')}  id={ev.get('id')}  "
            f"ext={ev.get('external_id')}"
        )


def maybe_force_garmin(
    api_key: str,
    *,
    dry_run: bool,
    enabled: bool,
    oldest: str | None = None,
    newest: str | None = None,
) -> None:
    """
    Optionally force Intervals→Garmin planned-workout re-upload.

    Args:
        api_key: Intervals API key.
        dry_run: If True, print intent only.
        enabled: If False, skip sync.
        oldest: Optional clear/nudge range start.
        newest: Optional clear/nudge range end.

    Returns:
        Prints sync status lines.
    """
    if not enabled:
        print("  garmin sync: skipped (--no-garmin-sync)")
        return
    if dry_run:
        print("  garmin sync: would force re-upload (toggle upload_workouts)")
        return
    result = force_garmin_workout_sync(api_key)
    before = result["before"]
    after = result["after"]
    print(
        f"  garmin sync: forced via {result['method']}  "
        f"last_upload {before.get('last_upload')} → {after.get('last_upload')}"
    )
    if before.get("last_upload") == after.get("last_upload"):
        if oldest and newest:
            managed = [
                e
                for e in list_events(api_key, oldest=oldest, newest=newest)
                if str(e.get("external_id") or "").startswith("running-repo:")
            ]
            n = nudge_events_for_garmin(api_key, managed)
            status = garmin_upload_status(api_key)
            print(
                f"  garmin sync: nudged {n} event(s); "
                f"last_upload now {status.get('last_upload')}"
            )
            if status.get("last_upload") == before.get("last_upload"):
                print(
                    "  warning: Garmin last_upload still unchanged; "
                    "check Intervals → Settings → Garmin → Upload planned workouts"
                )
            else:
                print(
                    "  garmin: Intervals re-uploaded planned workouts to Garmin Connect. "
                    "Open the Garmin Connect app and sync the watch."
                )
        else:
            print(
                "  warning: icu_garmin_last_upload did not change; "
                "check Intervals → Settings → Garmin → Upload planned workouts"
            )
    else:
        print(
            "  garmin: Intervals re-uploaded planned workouts to Garmin Connect. "
            "Open the Garmin Connect app and sync the watch."
        )


def push_sessions(
    api_key: str,
    sessions: list[dict],
    *,
    plan_stem: str,
    intervals_only: bool,
    dry_run: bool,
    clear_oldest: str | None = None,
    clear_newest: str | None = None,
    garmin_sync: bool = True,
    today: date | None = None,
) -> int:
    """
    Upsert plan sessions from today onward and optionally sync Garmin.

    Args:
        api_key: Intervals API key (unused when dry_run).
        sessions: Session mappings to upload.
        plan_stem: Week plan stem for ``external_id`` values.
        intervals_only: If True, upload only ``kind=interval`` sessions.
        dry_run: If True, print payloads without calling the API.
        clear_oldest: Optional managed-event clear range start.
        clear_newest: Optional managed-event clear range end.
        garmin_sync: If True, force Intervals→Garmin re-upload.
        today: Override for past-day protection; defaults to local today.

    Returns:
        Number of sessions pushed (or dry-run counted).

    Raises:
        SystemExit: If nothing remains to push on/after today.
        ValueError: If a session entry is not a mapping.
    """
    today = today or date.today()
    past, sessions = partition_sessions(sessions, today=today)
    for s in past:
        print(
            f"  skip past day {s.get('date')} {s.get('name')} "
            "(never update days before today)"
        )
    if not sessions:
        raise SystemExit(
            f"Refusing upload: no sessions on or after today ({today.isoformat()}). "
            "Past days are never updated."
        )

    if clear_oldest and clear_newest:
        clamped = clamp_clear_range(clear_oldest, clear_newest, today=today)
        if clamped:
            clear_range(api_key, clamped[0], clamped[1], dry_run=dry_run)
        else:
            print(
                f"  clear skipped: range {clear_oldest}..{clear_newest} "
                f"is entirely before today ({today.isoformat()})"
            )

    pushed = 0
    event_days: list[str] = []
    for session in sessions:
        if not isinstance(session, dict):
            raise ValueError(f"session must be a mapping, got {session!r}")
        kind = str(session.get("kind") or "easy").lower()
        if intervals_only and kind != "interval":
            print(f"  skip {session.get('date')} {session.get('name')} (kind={kind})")
            continue
        uid = session_uid(plan_stem, session)
        payload = event_payload_from_session(session, uid=uid)
        sport = payload.get("type") or "Run"
        label = (
            f"{payload['start_date_local'][:10]}  {payload['name']}  "
            f"type={sport} kind={kind}  uid={uid}"
        )
        event_days.append(payload["start_date_local"][:10])
        if dry_run:
            print(f"  dry-run {label}")
            print("    description:")
            for line in str(payload["description"]).splitlines():
                print(f"      {line}")
            pushed += 1
            continue
        result = upsert_event(api_key, payload)
        eid = result.get("id") if isinstance(result, dict) else None
        steps = ((result or {}).get("workout_doc") or {}).get("steps") or []
        n_reps = sum(1 for s in steps if s.get("reps"))
        print(
            f"  upserted {label}"
            + (f"  id={eid}" if eid else "")
            + f"  steps={len(steps)} reps_blocks={n_reps}"
        )
        pushed += 1

    if not pushed:
        raise SystemExit(
            f"Refusing upload: nothing to push on or after today "
            f"({today.isoformat()}) after filters."
        )

    maybe_force_garmin(
        api_key,
        dry_run=dry_run,
        enabled=garmin_sync,
        oldest=min(event_days),
        newest=max(event_days),
    )
    return pushed


def run_demo(api_key: str, *, dry_run: bool, garmin_sync: bool) -> int:
    """
    Push a sample 5x1km interval workout (demo helper).

    Args:
        api_key: Intervals API key.
        dry_run: If True, print only.
        garmin_sync: If True, force Garmin re-upload after push.

    Returns:
        Number of sessions pushed.

    Raises:
        SystemExit: If the hardcoded demo day is before today.
    """
    today = date.today()
    demo_day = "2026-08-03"
    if date.fromisoformat(demo_day) < today:
        raise SystemExit(
            f"Refusing demo: {demo_day} is before today ({today.isoformat()})."
        )
    session = {
        "date": demo_day,
        "name": "5x1km",
        "type": "Run",
        "kind": "interval",
        "start_time": "08:00",
        "description": DEMO_DESCRIPTION.strip(),
    }
    print(f"Demo: 5x1km on {demo_day} (clear day, then push Garmin-ready steps)")
    return push_sessions(
        api_key,
        [session],
        plan_stem="demo",
        intervals_only=False,
        dry_run=dry_run,
        clear_oldest=demo_day,
        clear_newest=demo_day,
        garmin_sync=garmin_sync,
        today=today,
    )


def main() -> int:
    """
    CLI entry: push week-plan sessions to Intervals and force Garmin sync.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description="Push weekly plan sessions to Intervals.icu calendar."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Path or YYYY-MM-DD for plans/*-week.json (default: newest)",
    )
    parser.add_argument(
        "--intervals-only",
        action="store_true",
        help="Only push sessions with kind: interval",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print payloads; do not call the API",
    )
    parser.add_argument(
        "--demo-5x1km",
        action="store_true",
        help="Push a sample 5x1km workout for 2026-08-03 (ignores --plan)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not delete existing running-repo: events in the week range first",
    )
    parser.add_argument(
        "--no-garmin-sync",
        action="store_true",
        help="Do not force Intervals→Garmin planned-workout re-upload after push",
    )
    args = parser.parse_args()

    root = repo_root()
    api_key = "" if args.dry_run else load_api_key(root / ".env")
    garmin_sync = not args.no_garmin_sync
    today = date.today()

    if args.demo_5x1km:
        n = run_demo(api_key, dry_run=args.dry_run, garmin_sync=garmin_sync)
        print(f"Done ({n} session(s)).")
        return 0

    try:
        plan_path = resolve_week_json(
            str(args.plan) if args.plan else None
        )
    except FileNotFoundError as e:
        raise SystemExit(str(e)) from e

    week = load_week(plan_path)
    sessions = sessions_from_week(week)
    if not sessions:
        print(f"No runnable sessions in {plan_path} — nothing to push.")
        return 0

    refuse_past_plan(week, sessions, today=today)

    clear_oldest = clear_newest = None
    if not args.no_clear:
        clear_oldest, clear_newest = covers_from_week(week)

    print(f"Plan: {plan_path}  (today={today.isoformat()})")
    n = push_sessions(
        api_key,
        sessions,
        plan_stem=plan_path.stem,
        intervals_only=args.intervals_only,
        dry_run=args.dry_run,
        clear_oldest=clear_oldest,
        clear_newest=clear_newest,
        garmin_sync=garmin_sync,
        today=today,
    )
    print(f"Done ({n} session(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
