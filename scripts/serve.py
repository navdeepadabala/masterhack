#!/usr/bin/env python
"""serve — convenience script to launch the Argus Console dashboard.

Usage:
    python scripts/serve.py [--host HOST] [--port PORT]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from argus.console import run_server  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the Argus Console dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
