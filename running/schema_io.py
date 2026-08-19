"""Load and validate JSON data files against schemas under schemas/."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from running.paths import repo_root

try:
    import jsonschema
    from jsonschema.validators import validator_for
    from referencing import Registry, Resource
except ImportError as exc:  # pragma: no cover
    raise SystemExit("jsonschema is required. Run: uv sync") from exc


def strip_meta(obj: Any) -> Any:
    """Recursively drop keys whose names start with underscore."""
    if isinstance(obj, dict):
        return {k: strip_meta(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [strip_meta(x) for x in obj]
    return obj


def schemas_dir(*, root: Path | None = None) -> Path:
    """Return the repo schemas/ directory."""
    return (root or repo_root()) / "schemas"


def schema_filename(schema_name: str) -> str:
    """Normalise a schema name to a lowercase ``*.schema.json`` filename."""
    name = Path(schema_name).name.lower()
    if name.endswith(".schema.json"):
        return name
    stem = name.removesuffix(".json")
    return f"{stem}.schema.json"


def schema_path(schema_name: str, *, root: Path | None = None) -> Path:
    """Return the path to a schema file under schemas/."""
    path = schemas_dir(root=root) / schema_filename(schema_name)
    if not path.is_file():
        raise FileNotFoundError(f"Missing schema: {path}")
    return path


def load_schema(schema_name: str, *, root: Path | None = None) -> dict[str, Any]:
    """Load a JSON schema document by name."""
    data = json.loads(schema_path(schema_name, root=root).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{schema_filename(schema_name)}: must be a JSON object")
    return data


def schema_registry(*, root: Path | None = None) -> Registry:
    """Build a referencing registry for every ``*.schema.json`` under schemas/.

    Registers each document by its ``$id`` (when set) and by filename so
    cross-file ``$ref`` values such as ``session.schema.json`` resolve.

    Args:
        root: Optional repo root for locating ``schemas/``.

    Returns:
        A ``referencing.Registry`` populated with local schemas.
    """
    resources: list[tuple[str, Resource]] = []
    for path in sorted(schemas_dir(root=root).glob("*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: must be a JSON object")
        resource = Resource.from_contents(data)
        resources.append((path.name, resource))
        schema_id = data.get("$id")
        if isinstance(schema_id, str) and schema_id.strip():
            resources.append((schema_id, resource))
    return Registry().with_resources(resources)


def _jsonish(obj: Any) -> Any:
    """Convert dates, datetimes, and Paths into JSON-serialisable values."""
    if isinstance(obj, dict):
        return {k: _jsonish(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonish(x) for x in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def validate(
    data: Any,
    schema_name: str,
    *,
    root: Path | None = None,
    label: str | None = None,
) -> Any:
    """Validate ``data`` against ``schemas/<schema_name>.schema.json``.

    Strips underscore-prefixed meta keys first.

    Returns:
        The cleaned instance on success.

    Raises:
        ValueError: If the instance fails schema validation.
    """
    cleaned = strip_meta(_jsonish(data))
    schema = load_schema(schema_name, root=root)
    where = label or schema_name
    validator_cls = validator_for(schema)
    validator = validator_cls(schema, registry=schema_registry(root=root))
    try:
        validator.validate(cleaned)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise ValueError(f"{where} schema: {path}: {exc.message}") from exc
    return cleaned


def load(file: str | Path, schema_name: str, *, root: Path | None = None) -> Any:
    """Load a JSON file and validate it against its schema.

    Args:
        file: Path to a ``.json`` file.
        schema_name: Schema stem (e.g. ``week``).
        root: Optional repo root for locating ``schemas/``.

    Returns:
        The validated instance.

    Raises:
        FileNotFoundError: If ``file`` does not exist.
        ValueError: If the file is not JSON or fails the schema.
    """
    path = Path(file)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".json":
        raise ValueError(f"Unsupported data file type: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate(data, schema_name, root=root, label=path.name)
