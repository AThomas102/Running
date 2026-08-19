"""CLI smoke tests for gmt-now and week markdown render.

Ensures entry points still produce usable output offline.
"""

from __future__ import annotations

import sys
from pathlib import Path

from running.gmt_now import main as gmt_now_main
from running.week import load_week, write_week_markdown

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "weeks"


def test_gmt_now_cli_prints_iso_date(capsys, monkeypatch) -> None:
    """Print a GMT date line and ISO timestamp.

    Purpose:
        History/plan tagging depends on ``gmt-now`` output shapes.

    Remove when:
        ``gmt-now`` is retired.
    """
    monkeypatch.setattr(sys, "argv", ["gmt-now"])
    gmt_now_main()
    out = capsys.readouterr().out
    assert "date:" in out
    assert "iso:" in out
    assert "T" in out
    assert any(
        len(part) == 10 and part[4] == "-" and part[7] == "-"
        for line in out.splitlines()
        for part in line.split()
    )


def test_render_week_plan_writes_md_for_fixture(tmp_path: Path) -> None:
    """Write markdown for a valid week that reflects the run total.

    Purpose:
        Render path must stay usable for agents reviewing plans in chat/files.

    Remove when:
        Markdown render is dropped.
    """
    src = FIXTURES / "valid-week.json"
    json_path = tmp_path / "2026-09-07-week.json"
    json_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    week = load_week(json_path, root=FIXTURES.parent)
    md_path = write_week_markdown(
        json_path, tmp_path / "2026-09-07-week.md", root=FIXTURES.parent
    )
    text = md_path.read_text(encoding="utf-8")
    assert md_path.is_file()
    assert f"**~{week['run_total_km']}**" in text
    assert "12k easy + strides" in text
