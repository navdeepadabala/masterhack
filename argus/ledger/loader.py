"""The Ledger — Fail-closed artifact loader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Path to the Ledger artifacts directory
LEDGER_ROOT = Path(__file__).parent / "data"


@dataclass
class LedgerArtifact:
    """A versioned Ledger artifact."""

    name: str
    version: str
    generated_at: str
    data: dict[str, Any]
    path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "generated_at": self.generated_at,
            "data": self.data,
        }


def load_artifact(
    name: str,
    version: str | None = None,
    ledger_root: Path | None = None,
) -> LedgerArtifact:
    """Load a Ledger artifact by name and version.

    FAIL-CLOSED: if the artifact is missing or malformed, this raises an
    error. Never returns fabricated placeholder data.
    """
    root = ledger_root or LEDGER_ROOT
    if not root.exists():
        raise FileNotFoundError(
            f"Ledger root directory not found at {root}. "
            "Did you run the experiment pipeline first?"
        )

    # Find artifact directory
    artifact_dir = root / name
    if not artifact_dir.exists():
        raise FileNotFoundError(
            f"Artifact '{name}' not found in Ledger. Available: {list_artifacts(ledger_root)}"
        )

    # Find version file
    if version:
        artifact_file = artifact_dir / f"{version}.json"
    else:
        # Find latest version
        versions = sorted([p for p in artifact_dir.glob("*.json")])
        if not versions:
            raise FileNotFoundError(
                f"No versions found for artifact '{name}' in {artifact_dir}"
            )
        artifact_file = versions[-1]

    if not artifact_file.exists():
        raise FileNotFoundError(
            f"Version {version} not found for artifact '{name}'. "
            f"Looking in {artifact_dir}."
        )

    # Load and validate
    try:
        raw = artifact_file.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Artifact '{name}' version {version or 'latest'} is malformed: {e}"
        ) from e

    # Validate required fields
    if not isinstance(data, dict):
        raise ValueError(
            f"Artifact '{name}' version {version or 'latest'} is not a JSON object"
        )

    required_fields = ["name", "version", "generated_at", "data"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(
            f"Artifact '{name}' version {version or 'latest'} missing required fields: {missing}"
        )

    return LedgerArtifact(
        name=data["name"],
        version=data["version"],
        generated_at=data["generated_at"],
        data=data["data"],
        path=artifact_file,
    )


def list_artifacts(ledger_root: Path | None = None) -> list[str]:
    """List all available artifact names in the Ledger."""
    root = ledger_root or LEDGER_ROOT
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


def list_versions(artifact_name: str, ledger_root: Path | None = None) -> list[str]:
    """List all available versions of an artifact."""
    root = ledger_root or LEDGER_ROOT
    artifact_dir = root / artifact_name
    if not artifact_dir.exists():
        return []
    return sorted([p.stem for p in artifact_dir.glob("*.json")])


def save_artifact(
    name: str,
    data: dict[str, Any],
    version: str,
    ledger_root: Path | None = None,
) -> Path:
    """Save an artifact to the Ledger.

    Returns the path to the saved artifact.
    """
    root = ledger_root or LEDGER_ROOT
    artifact_dir = root / name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_file = artifact_dir / f"{version}.json"
    payload = {
        "name": name,
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    artifact_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return artifact_file


def load_experiment_results(
    experiment_id: str,
    ledger_root: Path | None = None,
) -> dict[str, Any]:
    """Load aggregated experiment results for a given experiment."""
    artifact = load_artifact("experiment_results", experiment_id, ledger_root)
    return artifact.data