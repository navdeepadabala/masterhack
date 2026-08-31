"""Wraith — Adaptive red-team policy (LinUCB contextual bandit + baselines)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from argus.wraith.config import WraithConfig


# ---------------------------------------------------------------------------
# Reward decomposition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RewardComponents:
    """Components of the reward signal (each logged separately)."""

    fidelity_value: float  # Approved value (only if attacker evaded)
    detection_cost: float  # Cost from being detected (0 if evaded)
    resource_cost: float  # Fixed cost per attempt
    novelty_bonus: float  # One-shot bonus for first-novel-success
    total: float  # Sum of all components


# ---------------------------------------------------------------------------
# LinUCB implementation
# ---------------------------------------------------------------------------


@dataclass
class LinUCB:
    """Linear Upper Confidence Bound (LinUCB) contextual bandit.

    Operates over typed campaign parameters. Context per round = features
    summarizing recent Sentinel (defender) feedback only — no privileged
    access to Sentinel's internals.
    """

    n_arms: int
    context_dim: int
    alpha: float = 1.0
    ridge: float = 1.0

    def __post_init__(self) -> None:
        # Initialize A and b matrices per arm
        # A: (n_arms, d, d), b: (n_arms, d)
        self.A: list[np.ndarray] = [
            np.eye(self.context_dim) * self.ridge for _ in range(self.n_arms)
        ]
        self.b: list[np.ndarray] = [
            np.zeros(self.context_dim) for _ in range(self.n_arms)
        ]

    def select(self, contexts: np.ndarray) -> int:
        """Select arm using UCB rule given contexts (n_arms, d).

        Returns the chosen arm index.
        """
        # Validate input shape
        if contexts.ndim != 2:
            raise ValueError(
                f"contexts must be 2D (n_arms, d), got shape {contexts.shape}"
            )
        if contexts.shape != (self.n_arms, self.context_dim):
            raise ValueError(
                f"contexts shape {contexts.shape} != ({self.n_arms}, {self.context_dim})"
            )

        # Compute UCB for each arm
        ucbs = np.zeros(self.n_arms)
        for arm in range(self.n_arms):
            A_inv = np.linalg.inv(self.A[arm])
            theta = A_inv @ self.b[arm]
            x = contexts[arm]
            ucb = theta @ x + self.alpha * np.sqrt(x @ A_inv @ x)
            ucbs[arm] = ucb

        return int(np.argmax(ucbs))

    def update(self, arm: int, context: np.ndarray, reward: float) -> None:
        """Update the bandit's model for a single arm with one observation."""
        x = context.reshape(-1, 1)  # (d, 1)
        self.A[arm] = self.A[arm] + x @ x.T
        self.b[arm] = self.b[arm] + reward * x.flatten()


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


@dataclass
class RandomBaseline:
    """Pure random campaign selection."""

    n_arms: int
    seed: int = 42

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)

    def select(self, contexts: np.ndarray | None = None) -> int:
        return int(self.rng.integers(0, self.n_arms))

    def update(self, arm: int, context: np.ndarray, reward: float) -> None:
        # No learning
        pass


@dataclass
class RuleMutationBaseline:
    """Simple rule-mutation search.

    Starts with a baseline heuristic (lowest-indexed arm) and occasionally
    mutates to a random alternative.
    """

    n_arms: int
    seed: int = 42
    mutation_prob: float = 0.1

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)
        self.arm_counts = np.zeros(self.n_arms)
        self.arm_rewards = np.zeros(self.n_arms)
        self.last_arm = 0

    def select(self, contexts: np.ndarray | None = None) -> int:
        if self.rng.random() < self.mutation_prob:
            # Mutate to a random arm
            self.last_arm = int(self.rng.integers(0, self.n_arms))
        else:
            # Use greedy choice so far
            if self.arm_counts.sum() > 0:
                avg_rewards = np.divide(
                    self.arm_rewards,
                    self.arm_counts,
                    out=np.zeros_like(self.arm_rewards),
                    where=self.arm_counts > 0,
                )
                self.last_arm = int(np.argmax(avg_rewards))
            else:
                self.last_arm = 0
        return self.last_arm

    def update(self, arm: int, context: np.ndarray, reward: float) -> None:
        self.arm_counts[arm] += 1
        self.arm_rewards[arm] += reward


# ---------------------------------------------------------------------------
# Wraith policy: LinUCB + baselines + experiment orchestration
# ---------------------------------------------------------------------------


@dataclass
class WraithResult:
    """Aggregated results from a Wraith experiment run."""

    policy_name: str
    rewards_per_round: list[float] = field(default_factory=list)
    components_per_round: list[dict[str, float]] = field(default_factory=list)
    cumulative_rewards: list[float] = field(default_factory=list)
    avg_reward: float = 0.0
    n_rounds: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_name": self.policy_name,
            "rewards_per_round": self.rewards_per_round,
            "components_per_round": self.components_per_round,
            "cumulative_rewards": self.cumulative_rewards,
            "avg_reward": self.avg_reward,
            "n_rounds": self.n_rounds,
        }


# Type for the Defender's feedback function
FeedbackFn = Callable[[int, int], tuple[np.ndarray, float, dict[str, float]]]


@dataclass
class WraithPolicy:
    """Adaptive red-team policy using LinUCB + baselines.

    Operates over typed campaign parameters. Context per round = features
    summarizing recent Sentinel (defender) feedback only.
    """

    config: WraithConfig

    def __post_init__(self) -> None:
        self.linucb = LinUCB(
            n_arms=self.config.context_dim,  # Heuristic: dim arms
            context_dim=self.config.context_dim,
            alpha=self.config.alpha,
            ridge=self.config.ridge,
        )
        self.random_baseline = RandomBaseline(
            n_arms=self.config.context_dim,
            seed=self.config.random_seed,
        )
        self.rule_mutation_baseline = RuleMutationBaseline(
            n_arms=self.config.context_dim,
            seed=self.config.random_seed + 1,
        )

    def compute_reward(
        self,
        evaded: bool,
        approved_value: float,
        novelty: float = 0.0,
    ) -> RewardComponents:
        """Compute reward components for an attack attempt.

        Args:
            evaded: Whether the campaign evaded detection
            approved_value: Total value of payments approved (0 if detected)
            novelty: Novelty score 0-1 for this attack pattern
        """
        # Fidelity-weighted approved value
        fidelity_value = approved_value * self.config.fidelity_weight if evaded else 0.0
        # Detection cost (only if detected)
        detection_cost = self.config.detection_cost if not evaded else 0.0
        # Resource cost (always)
        resource_cost = self.config.resource_cost
        # Novelty bonus (only if evaded AND novelty > 0)
        novelty_bonus = (
            self.config.novelty_bonus * novelty
            if evaded and novelty > 0 and self.config.use_novelty_bonus
            else 0.0
        )
        total = fidelity_value - detection_cost - resource_cost + novelty_bonus

        return RewardComponents(
            fidelity_value=fidelity_value,
            detection_cost=detection_cost,
            resource_cost=resource_cost,
            novelty_bonus=novelty_bonus,
            total=total,
        )

    def run_experiment(
        self,
        feedback_fn: FeedbackFn,
        n_arms: int | None = None,
    ) -> dict[str, WraithResult]:
        """Run all three policies (LinUCB, random, rule mutation) under the same
        fixed campaign budget.

        Args:
            feedback_fn: Function (round, arm) -> (context_for_arms, reward_scalar, info_dict)
            n_arms: Override number of arms (defaults to config.context_dim)
        """
        n_arms = n_arms or self.config.context_dim

        # Run three independent experiments
        results = {
            "wraith_linucb": self._run_linucb_experiment(feedback_fn, n_arms),
            "random": self._run_baseline_experiment(self.random_baseline, feedback_fn, n_arms),
            "rule_mutation": self._run_baseline_experiment(self.rule_mutation_baseline, feedback_fn, n_arms),
        }
        return results

    def _run_linucb_experiment(
        self,
        feedback_fn: FeedbackFn,
        n_arms: int,
    ) -> WraithResult:
        """Run LinUCB experiment for n_rounds rounds."""
        rewards = []
        components = []
        cumulative = []

        # Initialize contexts: all arms start with neutral context
        contexts = np.zeros((n_arms, self.config.context_dim))

        cum_reward = 0.0
        for round_idx in range(self.config.n_rounds):
            # Select arm via LinUCB
            arm = self.linucb.select(contexts)

            # Get feedback
            new_contexts, reward_total, info = feedback_fn(round_idx, arm)
            reward = reward_total
            rewards.append(reward)
            components.append(info)
            cum_reward += reward
            cumulative.append(cum_reward)

            # Update LinUCB for the chosen arm
            self.linucb.update(arm, contexts[arm], reward)

            # Update contexts for next round (using defender feedback)
            contexts = new_contexts

        avg_reward = sum(rewards) / len(rewards) if rewards else 0.0

        return WraithResult(
            policy_name="wraith_linucb",
            rewards_per_round=rewards,
            components_per_round=components,
            cumulative_rewards=cumulative,
            avg_reward=avg_reward,
            n_rounds=len(rewards),
        )

    def _run_baseline_experiment(
        self,
        baseline: RandomBaseline | RuleMutationBaseline,
        feedback_fn: FeedbackFn,
        n_arms: int,
    ) -> WraithResult:
        """Run a baseline experiment for n_rounds rounds."""
        rewards = []
        components = []
        cumulative = []

        # Initialize contexts: all arms start with neutral context
        contexts = np.zeros((n_arms, self.config.context_dim))

        cum_reward = 0.0
        for round_idx in range(self.config.n_rounds):
            # Select arm via baseline
            arm = baseline.select(contexts)

            # Get feedback
            new_contexts, reward_total, info = feedback_fn(round_idx, arm)
            reward = reward_total
            rewards.append(reward)
            components.append(info)
            cum_reward += reward
            cumulative.append(cum_reward)

            # Update baseline
            baseline.update(arm, contexts[arm], reward)

            # Update contexts for next round
            contexts = new_contexts

        policy_name = (
            "random" if isinstance(baseline, RandomBaseline) else "rule_mutation"
        )
        avg_reward = sum(rewards) / len(rewards) if rewards else 0.0

        return WraithResult(
            policy_name=policy_name,
            rewards_per_round=rewards,
            components_per_round=components,
            cumulative_rewards=cumulative,
            avg_reward=avg_reward,
            n_rounds=len(rewards),
        )