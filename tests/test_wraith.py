"""Tests for Wraith (Phase 4) — LinUCB bandit and reward correctness."""
from __future__ import annotations

import numpy as np
import pytest

from argus.wraith.policy import (
    LinUCB,
    RandomBaseline,
    RuleMutationBaseline,
    WraithPolicy,
    RewardComponents,
    WraithResult,
)
from argus.wraith.config import WraithConfig


class TestLinUCB:
    """LinUCB implementation correctness."""

    def test_linucb_initialization(self):
        bandit = LinUCB(n_arms=5, context_dim=8)
        assert len(bandit.A) == 5
        assert len(bandit.b) == 5
        assert bandit.A[0].shape == (8, 8)
        assert len(bandit.b[0]) == 8

    def test_linucb_select_returns_valid_arm(self):
        bandit = LinUCB(n_arms=5, context_dim=8)
        contexts = np.random.randn(5, 8)
        arm = bandit.select(contexts)
        assert 0 <= arm < 5

    def test_linucb_select_requires_correct_shape(self):
        bandit = LinUCB(n_arms=5, context_dim=8)
        with pytest.raises(ValueError, match="shape"):
            bandit.select(np.random.randn(5))  # wrong dims
        with pytest.raises(ValueError, match="shape"):
            bandit.select(np.random.randn(5, 10))  # wrong context_dim

    def test_linucb_update_changes_model(self):
        bandit = LinUCB(n_arms=3, context_dim=4)
        context = np.array([1.0, 0.0, 0.0, 0.0])
        A_before = bandit.A[0].copy()
        bandit.update(arm=0, context=context, reward=1.0)
        assert not np.allclose(bandit.A[0], A_before)

    def test_linucb_deterministic_with_same_context(self):
        bandit1 = LinUCB(n_arms=3, context_dim=4, ridge=1.0)
        bandit2 = LinUCB(n_arms=3, context_dim=4, ridge=1.0)
        contexts = np.array([[1.0, 0.0, 0.0, 0.0]] * 3)
        arm1 = bandit1.select(contexts)
        arm2 = bandit2.select(contexts)
        assert arm1 == arm2


class TestBaselines:
    """Baseline policies."""

    def test_random_baseline_selects_valid_arm(self):
        baseline = RandomBaseline(n_arms=5, seed=42)
        for _ in range(10):
            arm = baseline.select()
            assert 0 <= arm < 5

    def test_random_baseline_is_deterministic(self):
        rng = np.random.default_rng(42)
        baseline1 = RandomBaseline(n_arms=5, seed=100)
        baseline2 = RandomBaseline(n_arms=5, seed=100)
        arms1 = [baseline1.select() for _ in range(20)]
        arms2 = [baseline2.select() for _ in range(20)]
        assert arms1 == arms2

    def test_rule_mutation_baseline_updates(self):
        baseline = RuleMutationBaseline(n_arms=5, seed=42)
        context = np.zeros(8)
        baseline.update(arm=2, context=context, reward=1.0)
        assert baseline.arm_counts[2] == 1
        assert baseline.arm_rewards[2] == 1.0

    def test_rule_mutation_mutates_sometimes(self):
        baseline = RuleMutationBaseline(n_arms=5, seed=42, mutation_prob=0.9)
        arms = [baseline.select() for _ in range(10)]
        assert len(set(arms)) > 1, "With 90% mutation prob, should see variation"


class TestRewardComponents:
    """Reward computation correctness."""

    def test_reward_evaded_positive(self):
        config = WraithConfig(fidelity_weight=1.0, detection_cost=0.5, resource_cost=0.1)
        policy = WraithPolicy(config)
        reward = policy.compute_reward(evaded=True, approved_value=100.0)
        assert isinstance(reward, RewardComponents)
        assert reward.fidelity_value == 100.0
        assert reward.detection_cost == 0.0
        assert reward.resource_cost == 0.1
        assert reward.total == pytest.approx(100.0 - 0.1)

    def test_reward_detected_zero_fidelity(self):
        config = WraithConfig(fidelity_weight=1.0, detection_cost=0.5, resource_cost=0.1)
        policy = WraithPolicy(config)
        reward = policy.compute_reward(evaded=False, approved_value=100.0)
        assert reward.fidelity_value == 0.0
        assert reward.detection_cost == 0.5
        assert reward.resource_cost == 0.1
        assert reward.total == pytest.approx(-0.5 - 0.1)

    def test_novelty_bonus_respects_flag(self):
        config = WraithConfig(fidelity_weight=1.0, novelty_bonus=0.2, use_novelty_bonus=False)
        policy = WraithPolicy(config)
        reward = policy.compute_reward(evaded=True, approved_value=50.0, novelty=1.0)
        assert reward.novelty_bonus == 0.0

        config_on = WraithConfig(fidelity_weight=1.0, novelty_bonus=0.2, use_novelty_bonus=True)
        policy_on = WraithPolicy(config_on)
        reward_on = policy_on.compute_reward(evaded=True, approved_value=50.0, novelty=1.0)
        assert reward_on.novelty_bonus == pytest.approx(0.2)


class TestWraithResult:
    """WraithResult serialization."""

    def test_wraith_result_to_dict(self):
        result = WraithResult(
            policy_name="test",
            rewards_per_round=[1.0, 2.0, 3.0],
            cumulative_rewards=[1.0, 3.0, 6.0],
            avg_reward=2.0,
            n_rounds=3,
        )
        d = result.to_dict()
        assert d["policy_name"] == "test"
        assert d["avg_reward"] == 2.0
        assert d["n_rounds"] == 3


class TestExperimentOrchestration:
    """End-to-end experiment correctness."""

    def test_invalid_campaign_never_earns_reward(self):
        """This is a logical test: reward function must not return positive for invalid."""
        config = WraithConfig(fidelity_weight=1.0, detection_cost=1.0, resource_cost=0.1)
        policy = WraithPolicy(config)
        # Detected = resource cost only (negative)
        reward = policy.compute_reward(evaded=False, approved_value=0.0)
        assert reward.total < 0

    def test_feedback_fn_interface(self):
        """Feedback fn must return 3-tuple: contexts, scalar reward, components dict."""
        config = WraithConfig(context_dim=4, n_rounds=5)
        policy = WraithPolicy(config)

        feedback_fn = lambda r, a: (
            np.zeros((config.context_dim, config.context_dim)),
            1.0,
            {"fidelity_value": 1.0, "detection_cost": 0.0, "resource_cost": 0.0, "total": 1.0},
        )

        results = policy.run_experiment(feedback_fn)
        assert "wraith_linucb" in results
        assert "random" in results
        assert "rule_mutation" in results
        for name, result in results.items():
            assert isinstance(result, WraithResult)
            assert len(result.rewards_per_round) == config.n_rounds
