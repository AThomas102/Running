"""Download one calendar month of Intervals.icu activities into .cache/."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from running.intervals_lib import (
    fetch_month_activities,
    gmt_now_iso,
    load_api_key,
    render_month_md,
    repo_root,
    summarize,
)


def main() -> int:
    """
    CLI entry: download one month of Intervals activities into ``.cache/``.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description="Fetch Intervals.icu activities for a given month (YYYY-MM)."
    )
    parser.add_argument("month", help="Month as YYYY-MM, e.g. 2026-07")
    parser.add_argument(
        "--outdir",
        default=None,
        help="Output root (default: <repo>/.cache/intervals)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="API page size (default 100)",
    )
    args = parser.parse_args()

    root = repo_root()
    out_root = Path(args.outdir) if args.outdir else (root / ".cache" / "intervals")
    month_dir = out_root / args.month
    month_dir.mkdir(parents=True, exist_ok=True)

    api_key = load_api_key(root / ".env")
    fetched_at = gmt_now_iso()
    activities = fetch_month_activities(api_key, args.month, limit=args.limit)
    summary = summarize(activities)

    meta = {
        "fetched_at_gmt": fetched_at,
        "month": args.month,
        **summary,
        "source": "intervals.icu",
    }

    (month_dir / "activities.json").write_text(
        json.dumps(activities, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (month_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (month_dir / "month.md").write_text(
        render_month_md(args.month, activities, summary, fetched_at),
        encoding="utf-8",
    )

    print(f"Wrote {month_dir}")
    print(
        f"  activities={summary['activity_count']}  "
        f"run={summary['run_km']} km  ride={summary['ride_km']} km  "
        f"longest_run={summary['longest_run_km']} km"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
