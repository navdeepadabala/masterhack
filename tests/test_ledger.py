"""Tests for The Ledger (Phase 6) — fail-closed artifact loader and stats."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from argus.ledger.loader import (
    LedgerArtifact,
    load_artifact,
    list_artifacts,
    list_versions,
    save_artifact,
)
from argus.ledger.stats import (
    statistical_significance,
    compute_ci,
    reality_check,
)
from argus.ledger.runner import aggregate_results


class TestLedgerArtifact:
    """LedgerArtifact structure."""

    def test_artifact_to_dict(self):
        art = LedgerArtifact(
            name="test",
            version="1.0.0",
            generated_at="2026-01-01T00:00:00Z",
            data={"key": "value"},
            path=Path("/tmp/test.json"),
        )
        d = art.to_dict()
        assert d["name"] == "test"
        assert d["version"] == "1.0.0"
        assert d["data"]["key"] == "value"


class TestSaveAndLoad:
    """Save/load roundtrip."""

    def _temp_root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_save_and_load_roundtrip(self):
        root = self._temp_root()
        data = {"mean": 0.5, "std": 0.1}
        path = save_artifact("test_experiment", data, "1.0.0", ledger_root=root)
        assert path.exists()

        art = load_artifact("test_experiment", "1.0.0", ledger_root=root)
        assert art.name == "test_experiment"
        assert art.version == "1.0.0"
        assert art.data["mean"] == 0.5

    def test_load_latest_version(self):
        root = self._temp_root()
        save_artifact("exp", {"v": 1}, "1.0.0", ledger_root=root)
        save_artifact("exp", {"v": 2}, "2.0.0", ledger_root=root)
        save_artifact("exp", {"v": 3}, "3.0.0", ledger_root=root)

        art = load_artifact("exp", ledger_root=root)
        assert art.version == "3.0.0"
        assert art.data["v"] == 3

    def test_list_artifacts(self):
        root = self._temp_root()
        save_artifact("exp_a", {}, "1.0.0", ledger_root=root)
        save_artifact("exp_b", {}, "1.0.0", ledger_root=root)
        names = list_artifacts(root)
        assert set(names) == {"exp_a", "exp_b"}

    def test_list_versions(self):
        root = self._temp_root()
        save_artifact("exp", {"v": 1}, "1.0.0", ledger_root=root)
        save_artifact("exp", {"v": 2}, "2.0.0", ledger_root=root)
        versions = list_versions("exp", root)
        assert versions == ["1.0.0", "2.0.0"]


class TestFailClosed:
    """Fail-closed behavior: missing/malformed artifacts must raise."""

    def _temp_root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def test_missing_ledger_root_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_artifact("foo", ledger_root=Path("/nonexistent/path"))

    def test_missing_artifact_name_raises(self):
        root = self._temp_root()
        with pytest.raises(FileNotFoundError, match="not found"):
            load_artifact("nonexistent_artifact", ledger_root=root)

    def test_missing_version_raises(self):
        root = self._temp_root()
        save_artifact("exp", {}, "1.0.0", ledger_root=root)
        with pytest.raises(FileNotFoundError, match="not found"):
            load_artifact("exp", "99.99.99", ledger_root=root)

    def test_malformed_json_raises(self):
        root = self._temp_root()
        artifact_dir = root / "bad_artifact"
        artifact_dir.mkdir()
        (artifact_dir / "1.0.0.json").write_text("{ not json }", encoding="utf-8")

        with pytest.raises(ValueError, match="malformed"):
            load_artifact("bad_artifact", "1.0.0", ledger_root=root)

    def test_missing_required_fields_raises(self):
        root = self._temp_root()
        artifact_dir = root / "incomplete_artifact"
        artifact_dir.mkdir()
        # Missing required fields
        (artifact_dir / "1.0.0.json").write_text(
            json.dumps({"name": "x", "version": "1.0.0"}), encoding="utf-8"
        )

        with pytest.raises(ValueError, match="missing required fields"):
            load_artifact("incomplete_artifact", "1.0.0", ledger_root=root)

    def test_not_a_dict_raises(self):
        root = self._temp_root()
        artifact_dir = root / "not_dict_artifact"
        artifact_dir.mkdir()
        # Root is a list, not a dict
        (artifact_dir / "1.0.0.json").write_text(
            json.dumps([{"name": "x"}]), encoding="utf-8"
        )

        with pytest.raises(ValueError, match="not a JSON object"):
            load_artifact("not_dict_artifact", "1.0.0", ledger_root=root)


class TestStatistics:
    """Statistical helpers."""

    def test_wilcoxon_significant(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [0.5, 1.5, 2.5, 3.5, 4.5]
        result = statistical_significance(a, b)
        assert result["test"] == "wilcoxon"
        assert result["n_pairs"] == 5
        assert "p_value" in result
        assert "significant" in result

    def test_wilcoxon_insufficient_data(self):
        result = statistical_significance([1.0], [2.0])
        assert result["significant"] is False
        assert result["p_value"] == 1.0

    def test_compute_ci_bootstrap(self):
        vals = [0.1, 0.2, 0.3, 0.4, 0.5]
        ci = compute_ci(vals, method="bootstrap")
        assert "mean" in ci
        assert "std" in ci
        assert "ci_low" in ci
        assert "ci_high" in ci
        assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]

    def test_compute_ci_single_value(self):
        ci = compute_ci([0.5])
        assert ci["mean"] == 0.5
        assert ci["ci_low"] == ci["ci_high"] == 0.5

    def test_reality_check(self):
        result = reality_check(synthetic_precision=0.8, synthetic_prevalence=0.5)
        assert "synthetic_point" in result
        assert "realistic_points" in result
        assert result["synthetic_point"]["precision"] == 0.8
        assert result["synthetic_point"]["prevalence"] == 0.5
        # Realistic points should have lower precision at lower prevalence
        for pt in result["realistic_points"]:
            assert 0.0 <= pt["precision"] <= 1.0


class TestAggregateResults:
    """Results aggregation (without running full pipeline)."""

    def test_aggregate_empty(self):
        result = aggregate_results([])
        assert "policies" in result
        assert "significance" in result
        assert "sentinel_generation_trends" in result

    def test_aggregate_with_mock_data(self):
        # Mock per-seed results
        per_seed = [
            {
                "wraith_results": {
                    "wraith_linucb": {"rewards_per_round": [1.0, 2.0, 3.0]},
                    "random": {"rewards_per_round": [0.5, 1.0, 1.5]},
                    "rule_mutation": {"rewards_per_round": [0.8, 1.2, 2.0]},
                },
                "sentinel_generations": [
                    {"evaluation": {"roc_auc": 0.75, "recall": 0.6, "precision": 0.7}},
                    {"evaluation": {"roc_auc": 0.80, "recall": 0.65, "precision": 0.75}},
                    {"evaluation": {"roc_auc": 0.85, "recall": 0.70, "precision": 0.80}},
                ],
            },
        ]
        result = aggregate_results(per_seed)
        assert "policies" in result
        assert "significance" in result
        assert "sentinel_generation_trends" in result
