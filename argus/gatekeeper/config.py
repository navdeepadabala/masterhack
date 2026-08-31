"""Gatekeeper configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GatekeeperConfig:
    """Immutable configuration for Gatekeeper."""

    # Amount bounds
    min_amount: float = 0.01
    max_amount: float = 50000.0

    # Timing bounds
    max_inter_event_gap_seconds: float = 86400.0  # 24 hours
    min_inter_event_gap_seconds: float = 1.0

    # Campaign bounds
    min_events: int = 1
    max_events: int = 100

    # Behavioral plausibility
    max_events_per_hour: float = 50.0
    max_velocity_zscore: float = 5.0

    # Entity consistency
    max_entity_reuse: int = 50

    # Whether to enforce archetype consistency
    strict_archetype_match: bool = True