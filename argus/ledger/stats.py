"""The Ledger — Statistical analysis and reality-check helpers."""

from __future__ import annotations

import numpy as np
from scipy import stats


def statistical_significance(
    scores_a: list[float],
    scores_b: list[float],
    test: str = "wilcoxon",
) -> dict[str, float]:
    """Compute statistical significance between two paired score arrays.

    Default test is Wilcoxon signed-rank (paired, non-parametric).
    """
    a = np.asarray(scores_a)
    b = np.asarray(scores_b)
    n = min(len(a), len(b))

    if n < 2:
        return {"test": test, "n_pairs": int(n), "p_value": 1.0, "significant": False}

    if test == "wilcoxon":
        try:
            diff = a[:n] - b[:n]
            if np.all(diff == 0):
                return {
                    "test": "wilcoxon",
                    "n_pairs": int(n),
                    "statistic": 0.0,
                    "p_value": 1.0,
                    "significant": False,
                }
            stat, p = stats.wilcoxon(a[:n], b[:n])
            return {
                "test": "wilcoxon",
                "n_pairs": int(n),
                "statistic": float(stat),
                "p_value": float(p),
                "significant": bool(p < 0.05),
            }
        except Exception:
            # Fallback if all values are zero or something weird
            return {"test": "wilcoxon", "n_pairs": int(n), "p_value": 1.0, "significant": False}
    else:
        raise ValueError(f"Unknown test: {test}")


def compute_ci(
    values: list[float],
    confidence: float = 0.95,
    method: str = "bootstrap",
    n_bootstrap: int = 1000,
) -> dict[str, float]:
    """Compute confidence interval for a list of values.

    Methods:
        bootstrap: Non-parametric bootstrap
        t: Student's t-distribution (parametric)
    """
    arr = np.asarray(values, dtype=float)
    if len(arr) < 2:
        return {
            "mean": float(arr.mean()) if len(arr) > 0 else 0.0,
            "std": float(arr.std()) if len(arr) > 1 else 0.0,
            "ci_low": float(arr.mean()) if len(arr) > 0 else 0.0,
            "ci_high": float(arr.mean()) if len(arr) > 0 else 0.0,
            "confidence": confidence,
            "method": method,
        }

    mean = float(arr.mean())
    std = float(arr.std(ddof=1))

    if method == "t":
        n = len(arr)
        sem = std / np.sqrt(n)
        h = sem * stats.t.ppf((1 + confidence) / 2, n - 1)
        return {
            "mean": mean,
            "std": std,
            "ci_low": mean - h,
            "ci_high": mean + h,
            "confidence": confidence,
            "method": "t",
        }
    elif method == "bootstrap":
        rng = np.random.default_rng(42)
        n = len(arr)
        boot_means = []
        for _ in range(n_bootstrap):
            sample = rng.choice(arr, size=n, replace=True)
            boot_means.append(sample.mean())
        boot_means = np.asarray(boot_means)
        alpha = 1 - confidence
        ci_low = float(np.percentile(boot_means, 100 * alpha / 2))
        ci_high = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
        return {
            "mean": mean,
            "std": std,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "confidence": confidence,
            "method": "bootstrap",
        }
    else:
        raise ValueError(f"Unknown method: {method}")


def reality_check(
    synthetic_precision: float,
    synthetic_prevalence: float,
    target_prevalences: list[float] = (0.0001, 0.0002, 0.001, 0.01, 0.02),
) -> dict[str, Any]:
    """Compute realistic-base-rate reweighted precision.

    Given Sentinel's precision at synthetic prevalence, reweight it to
    realistic low base rates (e.g. ~0.01-0.02% for typical fraud).

    Returns a chart-friendly dict with synthetic vs realistic points.

    Note: The connecting trend between points is illustrative interpolation,
    NOT additional measured data.
    """
    # At a lower prevalence, precision typically degrades if recall is fixed.
    # Use a simple model: precision_new = precision_old * (prevalence_new / prevalence_old)^0.5
    # This is a heuristic that says: at lower prevalence, the false positive
    # rate starts to dominate.

    points = []
    for prev in sorted(target_prevalences):
        if prev >= synthetic_prevalence:
            ratio = 1.0
        else:
            ratio = (prev / synthetic_prevalence) ** 0.5
        adjusted_precision = min(1.0, synthetic_precision * ratio)
        points.append({
            "prevalence": prev,
            "precision": adjusted_precision,
        })

    return {
        "synthetic_point": {
            "prevalence": synthetic_prevalence,
            "precision": synthetic_precision,
        },
        "realistic_points": points,
        "method": "prevalence_reweight",
        "note": (
            "Trend is illustrative — only the synthetic point is a measured datapoint. "
            "Realistic points are reweighted estimates, not additional measurements."
        ),
    }