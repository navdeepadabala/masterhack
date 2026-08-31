"""The Ledger — Versioned evidence artifacts and reproducibility pipeline."""
from argus.ledger.loader import (
    LedgerArtifact,
    load_artifact,
    load_experiment_results,
    list_artifacts,
)
from argus.ledger.runner import (
    run_experiments,
    run_multi_seed_experiments,
    aggregate_results,
)
from argus.ledger.stats import (
    statistical_significance,
    reality_check,
    compute_ci,
)

__all__ = [
    "LedgerArtifact",
    "load_artifact",
    "load_experiment_results",
    "list_artifacts",
    "run_experiments",
    "run_multi_seed_experiments",
    "aggregate_results",
    "statistical_significance",
    "reality_check",
    "compute_ci",
]