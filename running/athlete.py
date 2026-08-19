"""Load machine-readable athlete anchors (Pace bands) from JSON."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from running.paths import data_root
from running.schema_io import load as load_json_schema


@dataclass(frozen=True)
class AthleteAnchors:
    """Durable training numbers used when rendering sessions.

    Args:
        slug: Athlete identifier (filename stem).
        easy_pace_ceiling: Slow end of the easy Pace band (mm:ss).
        easy_pace_floor: Fast end of the easy Pace band (mm:ss).
        pace_unit: Distance unit in Intervals Pace targets (``km`` or ``mi``).
    """

    slug: str
    easy_pace_ceiling: str
    easy_pace_floor: str
    pace_unit: str = "km"

    def easy_pace_target(self) -> str:
        """Return the Intervals easy Pace target string.

        Returns:
            Target such as ``8:00-5:30/km Pace``.
        """
        return (
            f"{self.easy_pace_ceiling}-{self.easy_pace_floor}"
            f"/{self.pace_unit} Pace"
        )


def athlete_json_path(athlete_field: str, *, root: Path | None = None) -> Path:
    """Resolve the athlete JSON sidecar from a week ``athlete`` field.

    Accepts ``athletes/<slug>.md`` or ``athletes/<slug>.json`` (or a bare
    slug). Always loads ``athletes/<slug>.json`` under the data root.

    Args:
        athlete_field: Value of the week ``athlete`` field.
        root: Personal-data or fixture root. Defaults to ``data_root()``.

    Returns:
        Path to ``athletes/<slug>.json``.
    """
    base = root if root is not None else data_root()
    text = str(athlete_field or "").strip()
    if not text:
        raise ValueError("week athlete field is empty")
    slug = Path(text).stem
    if not slug:
        raise ValueError(f"cannot derive athlete slug from {athlete_field!r}")
    return base / "athletes" / f"{slug}.json"


def load_athlete_anchors(
    athlete_field: str,
    *,
    root: Path | None = None,
) -> AthleteAnchors:
    """Load and validate athlete Pace-band anchors.

    Args:
        athlete_field: Week ``athlete`` path or slug.
        root: Personal-data or fixture root.

    Returns:
        Parsed ``AthleteAnchors``.

    Raises:
        FileNotFoundError: If the athlete JSON file is missing.
        ValueError: If the file fails the athlete schema.
    """
    path = athlete_json_path(athlete_field, root=root)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing athlete JSON {path} (required for Pace bands; "
            "copy templates/athlete.json to athletes/<slug>.json)"
        )
    data = load_json_schema(path, "athlete")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    unit = str(data.get("pace_unit") or "km")
    return AthleteAnchors(
        slug=str(data["slug"]),
        easy_pace_ceiling=str(data["easy_pace_ceiling"]),
        easy_pace_floor=str(data["easy_pace_floor"]),
        pace_unit=unit,
    )
