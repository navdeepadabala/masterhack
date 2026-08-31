"""Scout taxonomy — hand-authored attack archetypes and variants.

Archetypes are authored by hand as structured data. They are the only
vocabulary later phases are allowed to draw from. The canonical on-disk
artifact is ``data/scout/taxonomy.json``; this module re-exports it and
provides helpers for loading and validation.
"""
from __future__ import annotations

import json
from pathlib import Path

from argus.scout.schema import (
    Archetype,
    EventSequence,
    EventSpec,
    Taxonomy,
    load_taxonomy,
    validate_taxonomy,
)

DATA_PATH = Path(__file__).parent / "data" / "taxonomy.json"

TAXONOMY = load_taxonomy(DATA_PATH) if DATA_PATH.exists() else Taxonomy(
    version="0.0.0",
    generated_at="1970-01-01T00:00:00Z",
    archetypes=[],
)


def export_taxonomy(path: Path | str | None = None) -> Path:
    """Write the canonical taxonomy JSON to disk."""
    p = Path(path) if path else DATA_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(TAXONOMY.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return p


__all__ = [
    "TAXONOMY",
    "DATA_PATH",
    "load_taxonomy",
    "validate_taxonomy",
    "export_taxonomy",
    "Archetype",
    "EventSequence",
    "EventSpec",
]