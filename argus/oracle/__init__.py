"""Oracle — LLM narrative layer (design-time drafting, results narration, evidence chat)."""
from argus.oracle.client import (
    OracleClient,
    OracleConfig,
    OracleResponse,
    template_fallback,
)
from argus.oracle.uses import (
    draft_archetype_description,
    narrate_results,
    ask_evidence,
    oracle_status,
)

__all__ = [
    "OracleClient",
    "OracleConfig",
    "OracleResponse",
    "template_fallback",
    "draft_archetype_description",
    "narrate_results",
    "ask_evidence",
    "oracle_status",
]