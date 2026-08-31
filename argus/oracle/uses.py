"""Oracle — Three grounded use cases for the LLM client."""

from __future__ import annotations

import os
from typing import Any, Optional

from argus.oracle.client import OracleClient, OracleConfig, OracleResponse, template_fallback


def oracle_status() -> dict[str, Any]:
    """Return the current Oracle status (provider, key presence, available)."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic")
    client = OracleClient(OracleConfig(provider=provider))
    return {
        "provider": provider,
        "has_key": client.is_available(),
        "model": client.config.model,
    }


def draft_archetype_description(
    archetype: dict[str, Any],
    client: Optional[OracleClient] = None,
) -> OracleResponse:
    """Draft a plain-language description for a Scout archetype.

    Design-time use: human reviews and approves before saving.
    Oracle is NEVER used to generate new attack instructions.
    """
    client = client or OracleClient(OracleConfig())
    template = template_fallback("archetype_description", archetype)

    # Build prompt that asks the LLM to expand the structured fields
    prompt = (
        f"You are helping a fraud-detection researcher write a clear, "
        f"plain-language description of a known fraud attack pattern for "
        f"a defensive research artifact. You are NOT generating new attack "
        f"instructions — you are describing a pattern that has already been "
        f"documented in academic and industry literature.\n\n"
        f"Archetype: {archetype.get('name')}\n"
        f"Channel: {archetype.get('channel')}\n"
        f"Rail: {archetype.get('rail')}\n"
        f"Objective: {archetype.get('objective')}\n"
        f"Known mitigations: {', '.join(archetype.get('mitigations', []))}\n\n"
        f"Write a 2-3 sentence plain-language description (markdown, no headers):\n"
    )

    return client.query(
        prompt,
        template=template,
        kind="archetype_draft",
        archetype_id=archetype.get("id", ""),
    )


def narrate_results(
    artifact: dict[str, Any],
    client: Optional[OracleClient] = None,
) -> OracleResponse:
    """Narrate a Ledger experiment artifact in plain language.
    The actual numbers MUST be passed as structured input.
    """
    client = client or OracleClient(OracleConfig())

    # Extract key numbers
    aggregated = artifact.get("aggregated", {})
    policies = aggregated.get("policies", {})
    sig = aggregated.get("significance", {})
    sentinel = aggregated.get("sentinel_generation_trends", {})
    reality = aggregated.get("reality_check", {})

    template_data = {
        "n_policies": len(policies),
        "best_avg_reward": (
            max((p.get("mean_avg_reward", 0.0) for p in policies.values()), default=0.0)
        ),
        "sig_vs_random": sig.get("wraith_vs_random", {}).get("significant", False),
    }
    template = template_fallback("results_narration", template_data)

    # Pass actual numbers as structured input — LLM is NOT allowed to guess
    prompt = (
        f"You are writing a short plain-language summary for a dashboard "
        f"about a fraud-detection experiment. You will be given the actual "
        f"measured numbers below — DO NOT invent, extrapolate, or estimate. "
        f"If something is unclear, say so.\n\n"
        f"Policies compared (mean avg reward ± CI):\n"
    )
    for name, p in policies.items():
        prompt += (
            f"- {name}: {p.get('mean_avg_reward', 0.0):.3f} "
            f"[{p.get('ci_low', 0.0):.3f}, {p.get('ci_high', 0.0):.3f}]\n"
        )
    prompt += f"\nWraith vs random significance: {sig.get('wraith_vs_random', {})}\n"
    prompt += f"Wraith vs rule-mutation significance: {sig.get('wraith_vs_rule_mutation', {})}\n"
    prompt += f"\nSentinel generation trends (mean ± CI):\n"
    for key in ("roc_auc", "recall", "precision"):
        s = sentinel.get(key, {})
        prompt += f"- {key}: {s.get('mean', 0.0):.3f} [{s.get('ci_low', 0.0):.3f}, {s.get('ci_high', 0.0):.3f}]\n"
    prompt += f"\nReality check: synthetic precision at prevalence 0.5 = "
    prompt += f"{reality.get('synthetic_point', {}).get('precision', 'N/A')}.\n"
    prompt += f"\nWrite a 3-5 sentence summary. Use only the numbers above."
    prompt += f"\nMethodology note: {reality.get('note', '')}\n"

    return client.query(
        prompt,
        template=template,
        kind="results_narration",
        artifact_name=artifact.get("name", ""),
        artifact_version=artifact.get("version", ""),
    )


def ask_evidence(
    question: str,
    artifacts: list[dict[str, Any]],
    client: Optional[OracleClient] = None,
) -> OracleResponse:
    """Answer a user question about Argus results, grounded in Ledger artifacts.

    If the artifacts don't cover the question, the LLM should decline.
    """
    client = client or OracleClient(OracleConfig())

    template_data = {
        "topic": question,
        "artifact_excerpt": (
            artifacts[0].get("data", {}).get("aggregated", {}) if artifacts else "(no artifact)"
        ),
    }
    template = template_fallback("evidence_chat", template_data)

    if not client.is_available():
        # Per Phase 7 spec: chat is disabled when no key is configured
        response = OracleResponse(
            text=(
                "Oracle chat is disabled because no LLM API key is configured. "
                "Set LLM_PROVIDER and the matching API key env var (e.g. "
                "ANTHROPIC_API_KEY) and restart. You can still browse the "
                "Ledger artifacts directly via the dashboard."
            ),
            provider=client.config.provider,
            model=client.config.model,
            used_cache=False,
            degraded=True,
            metadata={"reason": "no_api_key"},
        )
        return response

    # Build a prompt that explicitly grounds in artifacts
    prompt = (
        f"You are answering a question about Argus experiment results.\n\n"
        f"USER QUESTION: {question}\n\n"
        f"RELEVANT LEDGER ARTIFACTS:\n"
    )
    for art in artifacts:
        prompt += (
            f"\n--- {art.get('name', '')} v{art.get('version', '')} "
            f"({art.get('generated_at', '')}) ---\n"
            f"{str(art.get('data', {}))[:3000]}\n"
        )
    prompt += (
        f"\nINSTRUCTIONS:\n"
        f"1. Answer ONLY using information present in the artifacts above.\n"
        f"2. If the artifacts don't cover the question, say so explicitly.\n"
        f"3. NEVER invent numbers, claims, or details not in the artifacts.\n"
        f"4. Cite the artifact (name + version) when you cite a number.\n"
    )

    return client.query(
        prompt,
        template=template,
        kind="evidence_chat",
        question=question,
        n_artifacts=len(artifacts),
    )