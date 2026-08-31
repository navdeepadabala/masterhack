#!/usr/bin/env python
"""run-demo — convenience script to run the full Argus Cycle and save evidence.

Usage:
    python scripts/run-demo.py [--n-seeds N] [--n-rounds N] [--n-campaigns N]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from argus.console import run_demo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full Argus Cycle and save evidence")
    parser.add_argument("--n-seeds", type=int, default=3, help="Number of random seeds (default: 3)")
    parser.add_argument("--n-rounds", type=int, default=20, help="Rounds per Wraith run (default: 20)")
    parser.add_argument("--n-campaigns", type=int, default=80, help="Campaigns per seed (default: 80)")
    args = parser.parse_args()

    now_str = datetime.now(timezone.utc).isoformat()
    print(f"[{now_str}] Running Argus Cycle...")
    print(f"  seeds: {args.n_seeds}, rounds: {args.n_rounds}, campaigns: {args.n_campaigns}")
    result = run_demo(
        n_seeds=args.n_seeds,
        n_rounds=args.n_rounds,
        n_campaigns_per_seed=args.n_campaigns,
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] Saved v{result['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
