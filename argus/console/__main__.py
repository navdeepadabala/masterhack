"""Argus Console CLI entry point."""
from __future__ import annotations

import argparse
import sys

from argus.console.server import run_demo, run_server


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for python -m argus.console."""
    parser = argparse.ArgumentParser(
        prog="python -m argus.console",
        description="Argus Console — Web dashboard and research runner",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # run-demo
    demo_parser = subparsers.add_parser("run-demo", help="Run the full Argus Cycle and save evidence")
    demo_parser.add_argument("--n-seeds", type=int, default=3, help="Number of random seeds (default: 3)")
    demo_parser.add_argument("--n-rounds", type=int, default=20, help="Rounds per Wraith run (default: 20)")
    demo_parser.add_argument("--n-campaigns", type=int, default=80, help="Campaigns per seed (default: 80)")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the web dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")

    args = parser.parse_args(argv)

    if args.command == "run-demo":
        run_demo(
            n_seeds=args.n_seeds,
            n_rounds=args.n_rounds,
            n_campaigns_per_seed=args.n_campaigns,
        )
        return 0
    elif args.command == "serve":
        run_server(host=args.host, port=args.port)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
