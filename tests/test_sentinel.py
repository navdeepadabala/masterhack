"""Tests for Sentinel (Phase 5) — ensemble, splits, and split-disjointness."""
from __future__ import annotations

import numpy as np
import pytest

from argus.sentinel.split import (
    SplitConfig,
    Split,
    create_splits,
    check_split_disjointness,
)
from argus.sentinel.ensemble import (
    SentinelEnsemble,
    extract_features,
    extract_graph_features,
    build_feature_matrix,
    FEATURE_NAMES,
)
from argus.sentinel.config import SentinelConfig


class TestSplitConfig:
    """Split configuration validation."""

    def test_fractions_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            SplitConfig(train_frac=0.3, calib_frac=0.3, red_team_frac=0.3, harden_frac=0.1, holdout_frac=0.1)

    def test_valid_config(self):
        cfg = SplitConfig()
        assert cfg.train_frac == 0.4
        assert cfg.calib_frac == 0.2
        assert cfg.red_team_frac == 0.2
        assert cfg.harden_frac == 0.1
        assert cfg.holdout_frac == 0.1


class TestSplit:
    """Split data structure."""

    def test_split_len(self):
        s = Split(name="train")
        assert len(s) == 0

    def test_split_to_dict(self):
        s = Split(name="train")
        s.archetype_ids.add("card_craftering")
        d = s.to_dict()
        assert d["name"] == "train"
        assert "card_craftering" in d["archetype_ids"]


class TestSplitDisjointness:
    """Critical: splits must be campaign-id disjoint."""

    def _mock_campaign(self, cid: str, arch_id: str = "arch_a") -> object:
        """Minimal campaign-like object for split testing."""
        class C:
            id = cid
            archetype_id = arch_id
        return C()

    def test_no_overlap_regular_splits(self):
        campaigns = [self._mock_campaign(f"c_{i}") for i in range(100)]
        splits = create_splits(campaigns, SplitConfig(), holdout_archetype_ids=[])
        result = check_split_disjointness(splits)
        assert result["disjoint"], f"Unexpected overlaps: {result['overlaps']}"

    def test_holdout_contains_only_holdout_archetypes(self):
        campaigns = [self._mock_campaign(f"c_{i}", f"arch_{i % 3}") for i in range(50)]
        # arch_0 is held out
        splits = create_splits(campaigns, SplitConfig(), holdout_archetype_ids=["arch_0"])
        holdout = splits["holdout"]
        train = splits["train"]
        calib = splits["calib"]
        # Holdout should only contain arch_0
        assert all(c.archetype_id == "arch_0" for c in holdout.campaigns)
        # Train should not contain arch_0
        assert all(c.archetype_id != "arch_0" for c in train.campaigns)
        assert all(c.archetype_id != "arch_0" for c in calib.campaigns)

    def test_all_splits_disjoint_including_holdout(self):
        campaigns = [self._mock_campaign(f"c_{i}") for i in range(100)]
        splits = create_splits(campaigns, SplitConfig(), holdout_archetype_ids=["arch_0"])
        result = check_split_disjointness(splits)
        assert result["disjoint"], f"Overlaps: {result['overlaps']}"

    def test_split_disjointness_returns_sizes(self):
        campaigns = [self._mock_campaign(f"c_{i}") for i in range(40)]
        splits = create_splits(campaigns, SplitConfig(), holdout_archetype_ids=[])
        result = check_split_disjointness(splits)
        assert "sizes" in result
        assert sum(result["sizes"].values()) == 40


class TestFeatureExtraction:
    """Feature extraction from campaigns."""

    def test_extract_features_from_campaign(self):
        """Mock a campaign with features."""
        class MockCampaign:
            features = {
                "n_events": 5,
                "time_span_seconds": 3600.0,
                "avg_inter_event_gap": 720.0,
                "gap_std": 100.0,
                "n_payments": 3,
                "total_amount": 500.0,
                "avg_amount": 166.67,
                "amount_std": 50.0,
                "unique_entities": 4,
                "entity_reuse_ratio": 0.25,
                "max_entity_usage": 2,
                "events_per_hour": 5.0,
            }

        feats = extract_features(MockCampaign())
        assert len(feats) == len(FEATURE_NAMES)
        assert feats[0] == 5  # n_events

    def test_extract_graph_features(self):
        """Graph features computed from entity reuse."""
        class MockCampaign:
            features = {
                "entity_reuse_ratio": 0.5,
                "max_entity_usage": 5,
                "unique_entities": 10,
            }

        score = extract_graph_features(MockCampaign())
        assert 0.0 <= score <= 1.0


class TestSentinelEnsemble:
    """Ensemble model fitting and evaluation."""

    def test_ensemble_fit_and_predict(self):
        cfg = SentinelConfig(gb_n_estimators=10, isolation_n_estimators=10, random_seed=42)
        ensemble = SentinelEnsemble(cfg)

        # Create synthetic data: 50 legit (label=0) + 50 fraud (label=1)
        np.random.seed(42)
        n = 50
        X_legit = np.random.randn(n, len(FEATURE_NAMES)) * 0.5
        X_fraud = np.random.randn(n, len(FEATURE_NAMES)) * 0.5 + 2.0
        X_train = np.vstack([X_legit, X_fraud])
        y_train = np.array([0] * n + [1] * n)

        # Calibration: small legitimate set
        X_calib = np.random.randn(20, len(FEATURE_NAMES)) * 0.5
        g_train = np.random.rand(2 * n) * 0.3
        g_calib = np.random.rand(20) * 0.3

        ensemble.fit(X_train, y_train, X_calib, g_train, g_calib)
        assert ensemble.gb_trained
        assert ensemble.threshold > 0

    def test_ensemble_evaluate(self):
        cfg = SentinelConfig(gb_n_estimators=10, isolation_n_estimators=10, random_seed=42)
        ensemble = SentinelEnsemble(cfg)

        np.random.seed(42)
        n = 50
        X_train = np.random.randn(n, len(FEATURE_NAMES))
        y_train = np.array([0] * 25 + [1] * 25)
        X_calib = np.random.randn(20, len(FEATURE_NAMES)) * 0.5
        g_train = np.zeros(2 * n)
        g_calib = np.zeros(20)

        ensemble.fit(X_train, y_train, X_calib, g_train, g_calib)

        # Evaluate on test data
        X_test = np.random.randn(n, len(FEATURE_NAMES))
        y_test = np.array([0] * 25 + [1] * 25)
        metrics = ensemble.evaluate(X_test, y_test)
        assert "roc_auc" in metrics
        assert "recall" in metrics
        assert "precision" in metrics
        assert "threshold" in metrics
        assert 0.0 <= metrics["recall"] <= 1.0
        assert 0.0 <= metrics["precision"] <= 1.0
