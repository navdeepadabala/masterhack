"""Scout — Typed attack taxonomy.

Archetypes are hand-authored, versioned, structured scenario schemas. They are
the only vocabulary later phases (Forge, Gatekeeper, Wraith, Sentinel) are
allowed to draw from. They are never free-form "generate an attack" endpoints.
"""
from argus.scout.schema import (
    ACTOR_ROLES,
    CHANNELS,
    RAILS,
    EVENT_TYPES,
    Archetype,
    EventSpec,
    EventSequence,
    Taxonomy,
    load_taxonomy,
    validate_taxonomy,
)
from argus.scout.taxonomy import TAXONOMY

__all__ = [
    "ACTOR_ROLES",
    "CHANNELS",
    "RAILS",
    "EVENT_TYPES",
    "Archetype",
    "EventSpec",
    "EventSequence",
    "Taxonomy",
    "load_taxonomy",
    "validate_taxonomy",
    "TAXONOMY",
]