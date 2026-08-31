"""Sentinel configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SentinelConfig:
    """Configuration for the Sentinel defender ensemble."""

    # Model hyperparameters
    gb_n_estimators: int = 100
    gb_learning_rate: float = 0.1
    gb_max_depth: int = 3
    isolation_n_estimators: int = 100
    isolation_max_samples: str = "auto"
    isolation_contamination: float = 0.1

    # Feature weights for ensemble combination
    gb_weight: float = 0.5
    isolation_weight: float = 0.3
    graph_weight: float = 0.2

    # Threshold tuning
    target_precision: float = 0.9
    min_recall: float = 0.1

    # Splitting
    train_frac: float = 0.4
    calib_frac: float = 0.2
    red_team_frac: float = 0.2
    harden_frac: float = 0.1
    holdout_frac: float = 0.1

    # Whether to use graph/risk features
    use_graph_features: bool = True

    # Random seed for reproducibility
    random_seed: int = 42