"""Plans directory and week JSON file resolution."""

from __future__ import annotations

from pathlib import Path

from running.paths import data_root


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


def week_data_root(week_path: Path, *, root: Path | None = None) -> Path:
    """Infer the personal-data / fixture root for a week JSON file.

    Prefers an explicit ``root``. Otherwise, if the week lives in ``plans/``
    (live data) or ``weeks/`` (test fixtures) and a sibling ``athletes/``
    directory exists, use that parent. Else ``data_root()``.

    Args:
        week_path: Path to a ``*-week.json`` file.
        root: Optional override root.

    Returns:
        Directory that holds ``athletes/``.
    """
    if root is not None:
        return root
    parent = week_path.resolve().parent
    if parent.name in {"plans", "weeks"}:
        candidate = parent.parent
        if (candidate / "athletes").is_dir():
            return candidate
    return data_root()
