"""Sentinel data splits — disjoint partitions for training/eval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from argus.forge.simulator import Campaign


@dataclass(frozen=True)
class SplitConfig:
    """Configuration for dataset splitting."""

    train_frac: float = 0.4
    calib_frac: float = 0.2
    red_team_frac: float = 0.2
    harden_frac: float = 0.1
    holdout_frac: float = 0.1
    seed: int = 42

    def __post_init__(self) -> None:
        total = (
            self.train_frac
            + self.calib_frac
            + self.red_team_frac
            + self.harden_frac
            + self.holdout_frac
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Split fractions must sum to 1.0, got {total}")


@dataclass
class Split:
    """One split of the dataset."""

    name: str
    campaigns: list[Campaign] = field(default_factory=list)
    archetype_ids: set[str] = field(default_factory=set)

    def __len__(self) -> int:
        return len(self.campaigns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n_campaigns": len(self.campaigns),
            "archetype_ids": sorted(self.archetype_ids),
            "campaign_ids": [c.id for c in self.campaigns],
        }


def create_splits(
    campaigns: list[Campaign],
    config: SplitConfig | None = None,
    holdout_archetype_ids: list[str] | None = None,
) -> dict[str, Split]:
    """Create disjoint splits from a list of campaigns.

    Splits:
        train: Training data for supervised component
        calib: Calibration/validation split (legitimate-only)
        red_team: Wraith's search data
        harden: Hardening data for next generation
        holdout: Final held-out attack families (separate from all above)

    The holdout split contains WHOLE archetypes that are held out from every
    prior stage. This ensures we measure generalization to unseen attack families.
    """
    import random

    config = config or SplitConfig()
    holdout_archetype_ids = holdout_archetype_ids or []

    # Partition campaigns into "regular" (used for train/calib/red_team/harden)
    # and "holdout" (entire held-out archetypes)
    regular = []
    holdout_campaigns = []
    for c in campaigns:
        if c.archetype_id in holdout_archetype_ids:
            holdout_campaigns.append(c)
        else:
            regular.append(c)

    # Group regular campaigns by archetype to ensure archetype-level stratification
    by_archetype: dict[str, list[Campaign]] = {}
    for c in regular:
        by_archetype.setdefault(c.archetype_id, []).append(c)

    # Shuffle each archetype's campaigns with deterministic seed
    rng = random.Random(config.seed)
    for arch_campaigns in by_archetype.values():
        rng.shuffle(arch_campaigns)

    # Now allocate per archetype across splits
    splits = {
        "train": Split(name="train"),
        "calib": Split(name="calib"),
        "red_team": Split(name="red_team"),
        "harden": Split(name="harden"),
    }

    # Cumulative fractions
    cum_train = config.train_frac
    cum_calib = cum_train + config.calib_frac
    cum_red_team = cum_calib + config.red_team_frac
    cum_harden = cum_red_team + config.harden_frac

    for arch_id, arch_campaigns in by_archetype.items():
        n = len(arch_campaigns)
        train_end = int(n * cum_train)
        calib_end = int(n * cum_calib)
        red_team_end = int(n * cum_red_team)
        harden_end = int(n * cum_harden)

        splits["train"].campaigns.extend(arch_campaigns[:train_end])
        splits["calib"].campaigns.extend(arch_campaigns[train_end:calib_end])
        splits["red_team"].campaigns.extend(arch_campaigns[calib_end:red_team_end])
        splits["harden"].campaigns.extend(arch_campaigns[red_team_end:harden_end])
        # Remaining (if any rounding) goes into harden
        splits["harden"].campaigns.extend(arch_campaigns[harden_end:])

        for s in splits.values():
            s.archetype_ids.add(arch_id)

    # Holdout split
    holdout_split = Split(name="holdout")
    holdout_split.campaigns = holdout_campaigns
    holdout_split.archetype_ids = set(holdout_archetype_ids)
    splits["holdout"] = holdout_split

    return splits


def check_split_disjointness(splits: dict[str, Split]) -> dict[str, Any]:
    """Verify that splits are disjoint at the campaign-id level.

    Returns a dict with 'disjoint' (bool) and any overlapping campaign ids per pair.
    """
    ids_per_split: dict[str, set[str]] = {
        name: {c.id for c in split.campaigns} for name, split in splits.items()
    }
    overlaps: dict[str, list[str]] = {}
    names_list = list(splits.keys())

    for i, a in enumerate(names_list):
        for b in names_list[i + 1 :]:
            shared = sorted(ids_per_split[a] & ids_per_split[b])
            if shared:
                overlaps[f"{a}_{b}"] = shared

    return {
        "disjoint": len(overlaps) == 0,
        "overlaps": overlaps,
        "sizes": {name: len(ids_per_split[name]) for name in names_list},
    }