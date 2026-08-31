"""Forge and Gatekeeper configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ForgeConfig:
    """Immutable configuration for the Forge simulator."""

    # Campaign bounds
    min_events: int = 5
    max_events: int = 20

    # Timing parameters
    base_inter_event_gap_seconds: float = 300.0
    gap_noise_factor: float = 0.5

    # Amount parameters
    amount_noise_factor: float = 0.1

    # Entity pool sizes
    n_customers: int = 500
    n_devices: int = 750
    n_merchants: int = 100
    n_beneficiaries: int = 200
    n_cards: int = 600
    n_accounts: int = 500

    # Determinism
    rng_seed: int = 42

    # Archetype sampling weights
    archetype_weights: dict[str, float] = field(default_factory=dict)

    def with_seed(self, seed: int) -> "ForgeConfig":
        """Return a new config with a different seed."""
        return ForgeConfig(
            min_events=self.min_events,
            max_events=self.max_events,
            base_inter_event_gap_seconds=self.base_inter_event_gap_seconds,
            gap_noise_factor=self.gap_noise_factor,
            amount_noise_factor=self.amount_noise_factor,
            n_customers=self.n_customers,
            n_devices=self.n_devices,
            n_merchants=self.n_merchants,
            n_beneficiaries=self.n_beneficiaries,
            n_cards=self.n_cards,
            n_accounts=self.n_accounts,
            rng_seed=seed,
            archetype_weights=self.archetype_weights,
        )


@dataclass(frozen=True)
class GatekeeperConfig:
    """Configuration for Gatekeeper campaign validation."""

    # Campaign bounds
    min_events: int = 5
    max_events: int = 20

    # Timing bounds
    min_inter_event_gap_seconds: float = 0.0
    max_inter_event_gap_seconds: float = 3600.0

    # Amount bounds
    min_amount: float = 0.0
    max_amount: float = 1_000_000.0

    # Archetype validation
    strict_archetype_match: bool = True


class ForgeParams(BaseModel):
    """Runtime parameters for a single campaign generation."""

    seed: int = Field(..., ge=0)
    archetype_id: str = Field(..., min_length=1)
    variant_name: str = Field(..., min_length=1)
    config: ForgeConfig | None = None

    def resolve_config(self) -> ForgeConfig:
        """Resolve the runtime Forge configuration."""
        return self.config or ForgeConfig(rng_seed=self.seed)