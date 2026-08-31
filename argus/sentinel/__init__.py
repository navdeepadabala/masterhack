"""Sentinel — Fraud-defender ensemble and hardening loop."""
from argus.sentinel.split import (
    SplitConfig,
    Split,
    create_splits,
    check_split_disjointness,
)
from argus.sentinel.config import SentinelConfig
from argus.sentinel.ensemble import (
    SentinelEnsemble,
    build_feature_matrix,
    extract_features,
    extract_graph_features,
    FEATURE_NAMES,
)
from argus.sentinel.train import (
    TrainingResult,
    train_generation,
    train_generations,
    evaluate_generations,
)

__all__ = [
    "SplitConfig",
    "Split",
    "create_splits",
    "check_split_disjointness",
    "SentinelConfig",
    "SentinelEnsemble",
    "TrainingResult",
    "build_feature_matrix",
    "extract_features",
    "extract_graph_features",
    "FEATURE_NAMES",
    "train_generation",
    "train_generations",
    "evaluate_generations",
]