"""Render plans/*-week.yaml → matching markdown for reading."""

from __future__ import annotations

import argparse

from running.week_plan import resolve_week_yaml, write_week_markdown


def main() -> int:
    """
    CLI entry: render a week YAML to markdown.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description="Render weekly plan YAML to markdown (SSOT → readable view)."
    )
    parser.add_argument(
        "week",
        nargs="?",
        default=None,
        help="Path, YYYY-MM-DD, or omit for newest plans/*-week.yaml",
    )
    args = parser.parse_args()
    yaml_path = resolve_week_yaml(args.week)
    out = write_week_markdown(yaml_path)
    print(f"Wrote {out} (from {yaml_path.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
