"""data_root() env vs explicit root (tests must never use OneDrive)."""

from __future__ import annotations

from pathlib import Path

from running.paths import DATA_DIR_ENV, data_root, repo_root
from running.week_plan import plans_dir


def test_data_root_uses_env_when_no_root(monkeypatch: object, tmp_path: Path) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    monkeypatch.setattr("running.paths.load_dotenv", lambda root=None: None)
    assert data_root() == tmp_path
    assert plans_dir() == tmp_path / "plans"


def test_explicit_root_wins_over_env(monkeypatch: object, tmp_path: Path) -> None:
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv(DATA_DIR_ENV, str(env_dir))
    assert data_root(repo) == repo
    assert plans_dir(repo) == repo / "plans"


def test_unset_env_is_repo_root(monkeypatch: object) -> None:
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setattr("running.paths.load_dotenv", lambda root=None: None)
    assert data_root() == repo_root()
