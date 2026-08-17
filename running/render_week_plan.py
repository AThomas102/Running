"""Render plans/*-week.json → matching markdown for reading."""

from __future__ import annotations

import argparse

from running.week_plan import resolve_week_json, write_week_markdown


def main() -> int:
    """CLI entry: render a week JSON to markdown.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description="Render weekly plan JSON to markdown (SSOT → readable view)."
    )
    parser.add_argument(
        "week",
        nargs="?",
        default=None,
        help="Path, YYYY-MM-DD, or omit for newest plans/*-week.json",
    )
    args = parser.parse_args()
    json_path = resolve_week_json(args.week)
    out = write_week_markdown(json_path)
    print(f"Wrote {out} (from {json_path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
