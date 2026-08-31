"""Sentinel ensemble — supervised + unsupervised + graph risk."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler

from argus.forge.simulator import Campaign
from argus.sentinel.config import SentinelConfig


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


FEATURE_NAMES = [
    "n_events",
    "time_span_seconds",
    "avg_inter_event_gap",
    "gap_std",
    "n_payments",
    "total_amount",
    "avg_amount",
    "amount_std",
    "unique_entities",
    "entity_reuse_ratio",
    "max_entity_usage",
    "events_per_hour",
]


def extract_features(campaign: Campaign) -> np.ndarray:
    """Extract feature vector from a campaign.

    Returns array of shape (d,) matching FEATURE_NAMES order.
    """
    feats = campaign.features
    return np.array([feats.get(name, 0.0) for name in FEATURE_NAMES], dtype=float)


def extract_graph_features(campaign: Campaign) -> float:
    """Compute explicit graph/risk score from entity-reuse signals.

    This is a heuristic: high entity reuse within a campaign suggests
    coordinated attack behavior. Returns a score in [0, 1].
    """
    # Simple heuristic based on campaign features
    reuse_ratio = campaign.features.get("entity_reuse_ratio", 0.0)
    max_usage = campaign.features.get("max_entity_usage", 0)
    unique_entities = campaign.features.get("unique_entities", 1)

    # Normalize and combine
    score = min(1.0, 0.5 * reuse_ratio + 0.5 * min(1.0, max_usage / 10.0))
    return float(score)


def build_feature_matrix(
    campaigns: list[Campaign],
    use_graph: bool = True,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Build feature matrix from campaigns.

    Returns (X, graph_scores) where X is (n, d) and graph_scores is (n,) or None.
    """
    X = np.vstack([extract_features(c) for c in campaigns])
    if use_graph:
        g = np.array([extract_graph_features(c) for c in campaigns], dtype=float)
        return X, g
    return X, None


# ---------------------------------------------------------------------------
# Ensemble model
# ---------------------------------------------------------------------------


@dataclass
class SentinelEnsemble:
    """Sentinel defender ensemble.

    Combines:
    1. Supervised gradient-boosted classifier
    2. Unsupervised IsolationForest anomaly score
    3. Explicit graph/risk score
    """

    config: SentinelConfig
    gb: GradientBoostingClassifier | None = None
    iso: IsolationForest | None = None
    scaler: StandardScaler | None = field(default_factory=StandardScaler)
    gb_trained: bool = False
    iso_trained: bool = False
    threshold: float = 0.5

    def __post_init__(self) -> None:
        self.gb = GradientBoostingClassifier(
            n_estimators=self.config.gb_n_estimators,
            learning_rate=self.config.gb_learning_rate,
            max_depth=self.config.gb_max_depth,
            random_state=self.config.random_seed,
        )
        self.iso = IsolationForest(
            n_estimators=self.config.isolation_n_estimators,
            max_samples=self.config.isolation_max_samples,
            contamination=self.config.isolation_contamination,
            random_state=self.config.random_seed,
        )

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_calib: np.ndarray,
        g_train: np.ndarray | None = None,
        g_calib: np.ndarray | None = None,
    ) -> "SentinelEnsemble":
        """Fit the ensemble on training data and calibrate threshold.

        Args:
            X_train: Training features (legitimate + fraud from train split)
            y_train: Training labels (0=legitimate, 1=fraud)
            X_calib: Calibration features (legitimate-only from calib split)
            g_train: Graph scores for training data
            g_calib: Graph scores for calibration data
        """
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_calib_scaled = self.scaler.transform(X_calib)

        # 1. Supervised component
        self.gb.fit(X_train_scaled, y_train)
        self.gb_trained = True

        # 2. Unsupervised component (fit on legitimate only)
        X_legit = X_train_scaled[y_train == 0]
        if len(X_legit) > 10:
            self.iso.fit(X_legit)
            self.iso_trained = True

        # 3. Calibrate threshold on legitimate data
        # We want high precision (low FPR) on legitimate
        if self.gb_trained:
            # Get scores on calibration (legitimate) data
            gb_scores = self.gb.predict_proba(X_calib_scaled)[:, 1]
            iso_scores = (
                -self.iso.score_samples(X_calib_scaled)
                if self.iso_trained
                else np.zeros_like(gb_scores)
            )
            g_scores = g_calib if g_calib is not None else np.zeros_like(gb_scores)

            # Combine
            combined = self._combine_scores(gb_scores, iso_scores, g_scores)

            # Find threshold achieving target precision
            # On legitimate data, all labels are 0 (negative class)
            # We want threshold such that precision is high
            # Actually: we want to find threshold that gives target FPR
            # Sort combined scores
            sorted_scores = np.sort(combined)
            # For FPR = 1 - target_precision, pick that percentile
            idx = int(len(sorted_scores) * self.config.target_precision)
            idx = min(max(idx, 0), len(sorted_scores) - 1)
            self.threshold = float(sorted_scores[idx])

        return self

    def _combine_scores(
        self,
        gb_scores: np.ndarray,
        iso_scores: np.ndarray,
        g_scores: np.ndarray,
    ) -> np.ndarray:
        """Combine three score vectors into one."""
        # Normalize each component to [0, 1] range
        gb_norm = (gb_scores - gb_scores.min()) / (gb_scores.max() - gb_scores.min() + 1e-8)
        iso_norm = (
            (iso_scores - iso_scores.min()) / (iso_scores.max() - iso_scores.min() + 1e-8)
            if iso_scores.std() > 0
            else np.zeros_like(iso_scores)
        )
        g_norm = (
            (g_scores - g_scores.min()) / (g_scores.max() - g_scores.min() + 1e-8)
            if g_scores.std() > 0
            else np.zeros_like(g_scores)
        )

        return (
            self.config.gb_weight * gb_norm
            + self.config.isolation_weight * iso_norm
            + self.config.graph_weight * g_norm
        )

    def predict_scores(self, X: np.ndarray, g: np.ndarray | None = None) -> np.ndarray:
        """Return combined anomaly scores for campaigns."""
        X_scaled = self.scaler.transform(X)
        gb_scores = self.gb.predict_proba(X_scaled)[:, 1] if self.gb_trained else np.zeros(len(X))
        iso_scores = (
            -self.iso.score_samples(X_scaled)
            if self.iso_trained
            else np.zeros(len(X))
        )
        g_scores = g if g is not None else np.zeros(len(X))
        return self._combine_scores(gb_scores, iso_scores, g_scores)

    def predict(self, X: np.ndarray, g: np.ndarray | None = None) -> np.ndarray:
        """Binary predictions using calibrated threshold."""
        scores = self.predict_scores(X, g)
        return (scores >= self.threshold).astype(int)

    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        g: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Evaluate the ensemble on labeled data."""
        from sklearn.metrics import roc_auc_score, recall_score, precision_score, f1_score

        scores = self.predict_scores(X, g)
        preds = self.predict(X, g)

        return {
            "roc_auc": float(roc_auc_score(y, scores)),
            "recall": float(recall_score(y, preds, zero_division=0)),
            "precision": float(precision_score(y, preds, zero_division=0)),
            "f1": float(f1_score(y, preds, zero_division=0)),
            "threshold": self.threshold,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": self.config.__dict__,
            "threshold": self.threshold,
            "gb_trained": self.gb_trained,
            "iso_trained": self.iso_trained,
        }