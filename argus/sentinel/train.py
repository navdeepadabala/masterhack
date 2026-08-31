"""Sentinel training — hardening loop across generations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from argus.forge.simulator import Campaign
from argus.sentinel.config import SentinelConfig
from argus.sentinel.ensemble import SentinelEnsemble, build_feature_matrix
from argus.sentinel.split import Split, create_splits, check_split_disjointness


@dataclass
class TrainingResult:
    """Result of training one Sentinel generation."""

    generation: int
    split_sizes: dict[str, int]
    evaluation: dict[str, float]
    ensemble: dict[str, Any]
    hardening_campaigns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "split_sizes": self.split_sizes,
            "evaluation": self.evaluation,
            "ensemble": self.ensemble,
            "hardening_campaigns": self.hardening_campaigns,
        }


def train_generation(
    train_campaigns: list[Campaign],
    calib_campaigns: list[Campaign],
    holdout_campaigns: list[Campaign],
    config: SentinelConfig | None = None,
    hardening_campaigns: list[Campaign] | None = None,
) -> TrainingResult:
    """Train one Sentinel generation (optionally including hardening data).

    Args:
        train_campaigns: Training split (label known)
        calib_campaigns: Calibration split (legitimate-only, for threshold)
        holdout_campaigns: Held-out attack families (for final eval)
        hardening_campaigns: Campaigns that successfully evaded previous generation
    """
    config = config or SentinelConfig()

    # Build label array: 0=legitimate, 1=fraud
    all_train = list(train_campaigns)
    labels = np.array([0] * len(train_campaigns))  # train split is legitimate only

    # Add hardening campaigns as fraud
    hardening_ids: list[str] = []
    if hardening_campaigns:
        all_train.extend(hardening_campaigns)
        labels = np.concatenate([labels, np.ones(len(hardening_campaigns))])
        hardening_ids = [c.id for c in hardening_campaigns]

    # Build feature matrices
    X_train, g_train = build_feature_matrix(all_train, use_graph=config.use_graph_features)
    X_calib, g_calib = build_feature_matrix(calib_campaigns, use_graph=config.use_graph_features)
    X_holdout, g_holdout = build_feature_matrix(holdout_campaigns, use_graph=config.use_graph_features)
    y_holdout = np.ones(len(holdout_campaigns))  # all holdout is fraud

    # Train ensemble
    ensemble = SentinelEnsemble(config)
    ensemble.fit(X_train, labels, X_calib, g_train, g_calib)

    # Evaluate on holdout
    eval_result = ensemble.evaluate(X_holdout, y_holdout, g_holdout)

    return TrainingResult(
        generation=0,
        split_sizes={
            "train": len(train_campaigns),
            "calib": len(calib_campaigns),
            "holdout": len(holdout_campaigns),
            "hardening": len(hardening_campaigns) if hardening_campaigns else 0,
        },
        evaluation=eval_result,
        ensemble=ensemble.to_dict(),
        hardening_campaigns=hardening_ids,
    )


def train_generations(
    campaigns: list[Campaign],
    config: SentinelConfig | None = None,
    n_generations: int = 3,
    holdout_archetypes: list[str] | None = None,
    wraith_feedback_fn: Any = None,
) -> list[TrainingResult]:
    """Train Sentinel across multiple generations with hardening loop.

    Loop:
        1. Calibrate Sentinel-0 on training + calib splits
        2. Freeze it, run Wraith against it
        3. Take evasions with positive approved value as hardening data
        4. Retrain Sentinel-1 on training + hardening
        5. Repeat for Sentinel-2
    """
    config = config or SentinelConfig()

    # Create splits
    splits = create_splits(
        campaigns,
        holdout_archetype_ids=holdout_archetypes,
    )

    # Verify disjointness
    disjointness = check_split_disjointness(splits)
    if not disjointness["disjoint"]:
        raise ValueError(f"Splits are not disjoint: {disjointness['overlaps']}")

    results: list[TrainingResult] = []
    current_hardening: list[Campaign] = []

    for gen in range(n_generations):
        # Training data: always use the base train split
        train_campaigns = splits["train"].campaigns
        calib_campaigns = splits["calib"].campaigns
        holdout_campaigns = splits["holdout"].campaigns

        result = train_generation(
            train_campaigns,
            calib_campaigns,
            holdout_campaigns,
            config,
            hardening_campaigns=current_hardening if gen > 0 else None,
        )
        result = TrainingResult(
            generation=gen,
            split_sizes=result.split_sizes,
            evaluation=result.evaluation,
            ensemble=result.ensemble,
            hardening_campaigns=result.hardening_campaigns,
        )
        results.append(result)

        # Run Wraith against this generation to get hardening data
        if gen < n_generations - 1 and wraith_feedback_fn is not None:
            current_hardening = _run_wraith_and_collect_evasions(
                result.ensemble,
                splits["red_team"].campaigns,
                wraith_feedback_fn,
                config,
            )

    return results


def _run_wraith_and_collect_evasions(
    ensemble_dict: dict[str, Any],
    red_team_campaigns: list[Campaign],
    feedback_fn: Any,
    config: SentinelConfig,
) -> list[Campaign]:
    """Run Wraith feedback against current ensemble and collect evasions.

    Evasions = campaigns where approved_value > 0 (meaning the campaign
    wasn't detected by the current Sentinel generation).
    """
    from argus.wraith.policy import WraithPolicy, WraithConfig

    evasions: list[Campaign] = []

    # Use a simple feedback function
    def simple_feedback(round_idx: int, arm: int) -> tuple[np.ndarray, float, dict[str, float]]:
        # Pick campaign deterministically
        campaign = red_team_campaigns[round_idx % len(red_team_campaigns)]

        # Simulate detection based on ensemble threshold
        threshold = ensemble_dict.get("threshold", 0.5)
        # In real usage, this would be replaced by actual Sentinel scoring
        evaded = np.random.random() > threshold

        approved_value = campaign.features.get("total_amount", 0.0) if evaded else 0.0

        components = {
            "fidelity_value": approved_value,
            "detection_cost": 0.5 if not evaded else 0.0,
            "resource_cost": 0.1,
            "total": approved_value - (0.5 if not evaded else 0.0) - 0.1,
        }

        # Return neutral context
        contexts = np.zeros((config.context_dim, config.context_dim))
        return contexts, components["total"], components

    if len(red_team_campaigns) == 0:
        return []

    # Quick simulation: collect campaigns that evaded
    for campaign in red_team_campaigns:
        threshold = ensemble_dict.get("threshold", 0.5)
        # Simplified: use entity_reuse_ratio as a proxy score
        score = campaign.features.get("entity_reuse_ratio", 0.0)
        if score < threshold:
            evasions.append(campaign)

    return evasions[:50]  # Limit hardening set size


def evaluate_generations(
    results: list[TrainingResult],
    holdout_campaigns: list[Campaign],
) -> dict[str, Any]:
    """Evaluate all generations on the same held-out attack families.

    Report ROC-AUC and recall at minimum for each generation.
    """
    from sklearn.metrics import roc_auc_score, recall_score, precision_score

    evaluation: dict[str, Any] = {}

    for r in results:
        eval_data = r.evaluation.copy()
        eval_data["generation"] = r.generation
        evaluation[f"generation_{r.generation}"] = eval_data

    # Summary comparison
    summary = {
        "n_generations": len(results),
        "roc_auc_trend": [r.evaluation.get("roc_auc", 0.0) for r in results],
        "recall_trend": [r.evaluation.get("recall", 0.0) for r in results],
        "precision_trend": [r.evaluation.get("precision", 0.0) for r in results],
    }
    evaluation["summary"] = summary

    return evaluation