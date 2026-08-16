#!/usr/bin/env python3
"""Print the current date/time in GMT (UTC) for tagging history and plan files."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone


def main() -> None:
    """
    Print the current GMT/UTC timestamp for file tagging.

    Returns:
        Prints to stdout.
    """
    parser = argparse.ArgumentParser(
        description="Print current GMT/UTC timestamp for file tagging."
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=("date", "iso", "stamp", "all"),
        default="all",
        help="date=YYYY-MM-DD, iso=YYYY-MM-DDTHH:MM:SSZ, stamp=YYYYMMDDTHHMMSSZ, all=all three",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    values = {
        "date": now.strftime("%Y-%m-%d"),
        "iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stamp": now.strftime("%Y%m%dT%H%M%SZ"),
    }

    if args.format == "all":
        for key in ("date", "iso", "stamp"):
            print(f"{key}: {values[key]}")
    else:
        print(values[args.format])


if __name__ == "__main__":
    main()
