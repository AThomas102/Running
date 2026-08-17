"""Shared filesystem helpers."""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV = "RUNNING_DATA_DIR"


def repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent


def load_dotenv(root: Path | None = None) -> None:
    """Load unset keys from the repo `.env` into the process environment.

    Args:
        root: Repository root containing `.env`. Defaults to ``repo_root()``.
    """
    env_path = (root or repo_root()) / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def data_root(root: Path | None = None) -> Path:
    """Return the live personal-data directory.

    An explicit ``root`` is a repo (or pytest fixture) tree and wins over
    ``RUNNING_DATA_DIR`` so tests never write to OneDrive.

    With no ``root``, load the repo ``.env`` then prefer ``RUNNING_DATA_DIR``
    if set, else the repository root.

    Args:
        root: Optional repo/fixture root. When set, ignore the env var.

    Returns:
        Directory that holds ``athletes/``, ``history/``, and ``plans/``.
    """
    if root is not None:
        return root

    load_dotenv()
    env = (os.environ.get(DATA_DIR_ENV) or "").strip()
    if env:
        return Path(env).expanduser()
    return repo_root()
