"""Wraith configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WraithConfig:
    """Immutable configuration for Wraith (the red-team policy)."""

    # LinUCB parameters
    alpha: float = 1.0  # Exploration parameter (higher = more exploration)
    context_dim: int = 16  # Dimensionality of context vectors
    ridge: float = 1.0  # Ridge regularization for LinUCB

    # Reward weights
    detection_cost: float = 0.5  # Cost per detection (for evading = no cost)
    resource_cost: float = 0.1  # Cost per campaign attempt (regardless of outcome)
    fidelity_weight: float = 1.0  # Weight on fidelity component
    novelty_bonus: float = 0.2  # Bonus for first-novel-success
    use_novelty_bonus: bool = False  # Whether to apply novelty bonus

    # Experiment settings
    n_rounds: int = 100
    n_seeds: int = 5

    # Random baseline
    random_seed: int = 42