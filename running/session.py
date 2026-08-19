"""Structured run-session model (JSON → dataclasses → Intervals description)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Union, cast

from running.athlete import AthleteAnchors
from running.workout_syntax import (
    format_distance_km,
    format_duration_minutes,
    intensity_step_line,
    step_line,
)

Intensity = Literal["rest", "active", "warmup", "cooldown"]
AthleteBand = Literal["easy_pace"]


@dataclass(frozen=True)
class Target:
    """One structured intensity target for a step.

    Exactly one of ``athlete``, ``pace``, ``hr``, or ``intensity`` is set.
    """

    athlete: AthleteBand | None = None
    pace: str | None = None
    hr: str | None = None
    intensity: Intensity | None = None

    def resolve(self, anchors: AthleteAnchors) -> str:
        """Return the Intervals target token (Pace/HR) or intensity flag.

        Args:
            anchors: Athlete Pace bands for ``athlete`` targets.

        Returns:
            A guide-style Pace/HR string, or an ``intensity=…`` value.

        Raises:
            ValueError: If no target field is set or ``athlete`` is unknown.
        """
        if self.athlete == "easy_pace":
            return anchors.easy_pace_target()
        if self.athlete is not None:
            raise ValueError(f"unknown athlete band {self.athlete!r}")
        if self.pace is not None:
            text = self.pace.strip()
            if not text.lower().endswith("pace"):
                text = f"{text} Pace"
            return text
        if self.hr is not None:
            text = self.hr.strip()
            if not text.upper().endswith("HR") and not text.upper().endswith("LTHR"):
                text = f"{text} HR"
            return text
        if self.intensity is not None:
            return self.intensity
        raise ValueError("target has no athlete, pace, hr, or intensity field")

    def to_dict(self) -> dict[str, str]:
        """Serialize to the JSON target object."""
        if self.athlete is not None:
            return {"athlete": self.athlete}
        if self.pace is not None:
            return {"pace": self.pace}
        if self.hr is not None:
            return {"hr": self.hr}
        if self.intensity is not None:
            return {"intensity": self.intensity}
        raise ValueError("empty target")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Target:
        """Parse a JSON target object.

        Args:
            data: Mapping with one of ``athlete``, ``pace``, ``hr``, ``intensity``.

        Returns:
            A ``Target``.

        Raises:
            ValueError: If the mapping is not a single recognised field.
        """
        keys = [k for k in ("athlete", "pace", "hr", "intensity") if k in data]
        if len(keys) != 1:
            raise ValueError(f"target must have exactly one field, got {sorted(data)}")
        key = keys[0]
        if key == "athlete":
            band = str(data["athlete"])
            if band != "easy_pace":
                raise ValueError(f"unknown athlete band {band!r}")
            return cls(athlete="easy_pace")
        if key == "pace":
            return cls(pace=str(data["pace"]))
        if key == "hr":
            return cls(hr=str(data["hr"]))
        intensity = str(data["intensity"])
        allowed: frozenset[str] = frozenset({"rest", "active", "warmup", "cooldown"})
        if intensity not in allowed:
            raise ValueError(f"unknown intensity {intensity!r}")
        return cls(intensity=cast(Intensity, intensity))


@dataclass(frozen=True)
class Step:
    """One workout step: a load, a target, and optional note / press-lap."""

    target: Target
    km: float | None = None
    mtr: float | None = None
    seconds: int | None = None
    minutes: int | None = None
    press_lap: bool = False
    note: str | None = None

    def load_token(self) -> str:
        """Return the Intervals duration/distance token for this step.

        Returns:
            A guide-style load such as ``12km``, ``400mtr``, ``90s``, or ``15m``.

        Raises:
            ValueError: If no positive load is set.
        """
        if self.km is not None:
            return format_distance_km(self.km)
        if self.mtr is not None:
            if self.mtr <= 0:
                raise ValueError(f"mtr must be positive, got {self.mtr}")
            if float(self.mtr).is_integer():
                return f"{int(self.mtr)}mtr"
            return f"{self.mtr:g}mtr"
        if self.seconds is not None:
            if self.seconds <= 0:
                raise ValueError("seconds must be positive")
            return f"{self.seconds}s"
        if self.minutes is not None:
            return format_duration_minutes(self.minutes)
        raise ValueError("step needs km, mtr, seconds, or minutes")

    def distance_km(self) -> float:
        """Return planned running distance for this step (0 if time-only)."""
        if self.km is not None:
            return float(self.km)
        if self.mtr is not None:
            return float(self.mtr) / 1000.0
        return 0.0

    def has_distance_load(self) -> bool:
        """Return True if this step is specified as distance."""
        return self.km is not None or self.mtr is not None

    def to_intervals_line(self, anchors: AthleteAnchors) -> str:
        """Render one Intervals step line (no trailing extra blanks).

        Args:
            anchors: Athlete Pace bands.

        Returns:
            A line starting with ``- ``, ending with a newline.
        """
        load = self.load_token()
        if self.target.intensity is not None:
            return intensity_step_line(
                load,
                self.target.intensity,
                press_lap=self.press_lap,
                note=self.note,
            )
        if self.press_lap:
            raise ValueError("press_lap steps must use an intensity target")
        return step_line(load, self.target.resolve(anchors), note=self.note)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON step object."""
        out: dict[str, Any] = {"target": self.target.to_dict()}
        if self.km is not None:
            out["km"] = self.km
        if self.mtr is not None:
            out["mtr"] = self.mtr
        if self.seconds is not None:
            out["seconds"] = self.seconds
        if self.minutes is not None:
            out["minutes"] = self.minutes
        if self.press_lap:
            out["press_lap"] = True
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Step:
        """Parse a JSON step object."""
        target_raw = data.get("target")
        if not isinstance(target_raw, dict):
            raise ValueError("step.target must be an object")
        return cls(
            target=Target.from_dict(target_raw),
            km=float(data["km"]) if data.get("km") is not None else None,
            mtr=float(data["mtr"]) if data.get("mtr") is not None else None,
            seconds=int(data["seconds"]) if data.get("seconds") is not None else None,
            minutes=int(data["minutes"]) if data.get("minutes") is not None else None,
            press_lap=bool(data.get("press_lap") or False),
            note=str(data["note"]) if data.get("note") else None,
        )


@dataclass(frozen=True)
class Repeat:
    """A repeated block of steps (Intervals ``Nx`` header)."""

    reps: int
    steps: tuple[Step, ...]

    def distance_km(self) -> float:
        """Return distance of one inner set multiplied by ``reps``."""
        inner = sum(s.distance_km() for s in self.steps)
        return inner * self.reps

    def has_distance_load(self) -> bool:
        """Return True if any inner step is a distance load."""
        return any(s.has_distance_load() for s in self.steps)

    def to_intervals_text(self, anchors: AthleteAnchors) -> str:
        """Render the repeat header and inner steps.

        Args:
            anchors: Athlete Pace bands.

        Returns:
            Text ending with a newline.
        """
        if self.reps < 1:
            raise ValueError(f"reps must be >= 1, got {self.reps}")
        lines = [f"{self.reps}x"]
        for step in self.steps:
            lines.append(step.to_intervals_line(anchors).rstrip("\n"))
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON repeat object."""
        return {"reps": self.reps, "steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Repeat:
        """Parse a JSON repeat object."""
        raw_steps = data.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("repeat.steps must be a non-empty list")
        steps = tuple(Step.from_dict(s) for s in raw_steps if isinstance(s, dict))
        if len(steps) != len(raw_steps):
            raise ValueError("repeat.steps entries must be objects")
        return cls(reps=int(data["reps"]), steps=steps)


Block = Union[Step, Repeat]


def parse_block(data: dict[str, Any]) -> Block:
    """Parse a session block as a Repeat or Step.

    Args:
        data: JSON object with either ``reps`` or step fields.

    Returns:
        A ``Repeat`` or ``Step``.
    """
    if "reps" in data:
        return Repeat.from_dict(data)
    return Step.from_dict(data)


@dataclass(frozen=True)
class RunSession:
    """A complete run session: ordered steps and repeats."""

    blocks: tuple[Block, ...]
    name: str | None = None
    kind: str | None = None

    def distance_km(self) -> float:
        """Sum distance loads across blocks (repeats multiplied)."""
        return sum(b.distance_km() for b in self.blocks)

    def has_distance_load(self) -> bool:
        """Return True if any block specifies km or meters."""
        return any(b.has_distance_load() for b in self.blocks)

    def has_press_lap(self) -> bool:
        """Return True if any step uses an open press-lap rest."""
        for block in self.blocks:
            if isinstance(block, Step) and block.press_lap:
                return True
            if isinstance(block, Repeat):
                if any(s.press_lap for s in block.steps):
                    return True
        return False

    def to_intervals_description(self, anchors: AthleteAnchors) -> str:
        """Render a full Intervals workout description.

        Args:
            anchors: Athlete Pace bands for ``athlete`` targets.

        Returns:
            Description ending with a newline.
        """
        chunks: list[str] = []
        for block in self.blocks:
            if isinstance(block, Repeat):
                chunks.append(block.to_intervals_text(anchors).rstrip("\n"))
            else:
                chunks.append(block.to_intervals_line(anchors).rstrip("\n"))
        return "\n\n".join(chunks) + "\n"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON session object."""
        out: dict[str, Any] = {
            "blocks": [b.to_dict() for b in self.blocks]
        }
        if self.name:
            out["name"] = self.name
        if self.kind:
            out["kind"] = self.kind
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunSession:
        """Parse a JSON run session object.

        Args:
            data: Mapping with ``blocks`` and optional ``name`` / ``kind``.

        Returns:
            A ``RunSession``.

        Raises:
            ValueError: If ``blocks`` is missing or invalid.
        """
        raw_blocks = data.get("blocks")
        if not isinstance(raw_blocks, list) or not raw_blocks:
            raise ValueError("run.blocks must be a non-empty list")
        blocks: list[Block] = []
        for item in raw_blocks:
            if not isinstance(item, dict):
                raise ValueError("run.blocks entries must be objects")
            blocks.append(parse_block(item))
        name = data.get("name")
        kind = data.get("kind")
        return cls(
            blocks=tuple(blocks),
            name=str(name) if name else None,
            kind=str(kind) if kind else None,
        )
