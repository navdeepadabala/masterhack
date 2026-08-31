"""Gatekeeper checks — validity/fidelity firewall logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from argus.forge.simulator import Campaign, Event, Entity
from argus.gatekeeper.config import GatekeeperConfig
from argus.scout.schema import Archetype, EventSequence


class GatekeeperResult:
    """Result of a Gatekeeper check."""

    valid: bool
    reason: str | None = None
    reason_code: str | None = None
    invalid_components: list[dict[str, Any]] | None = None

    def __init__(
        self,
        valid: bool,
        reason: str | None = None,
        reason_code: str | None = None,
        invalid_components: list[dict[str, Any]] | None = None,
    ) -> None:
        self.valid = valid
        self.reason = reason
        self.reason_code = reason_code
        self.invalid_components = invalid_components

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "invalid_components": (
                self.invalid_components if self.invalid_components else []
            ),
        }


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def _check_min_max_events(campaign: Campaign, config: GatekeeperConfig) -> dict[str, Any]:
    """Check event count is within bounds."""
    n_events = len(campaign.events)
    if n_events < config.min_events:
        return {
            "passed": False,
            "reason": f"Campaign has {n_events} events, minimum is {config.min_events}",
            "reason_code": "EVENT_COUNT_LOW",
        }
    if n_events > config.max_events:
        return {
            "passed": False,
            "reason": f"Campaign has {n_events} events, maximum is {config.max_events}",
            "reason_code": "EVENT_COUNT_HIGH",
        }
    return {"passed": True, "reason": None, "reason_code": None}


def _check_event_chronology(campaign: Campaign) -> dict[str, Any]:
    """Check events are in chronological order."""
    timestamps = [event.timestamp for event in campaign.events]
    for i in range(1, len(timestamps)):
        if timestamps[i] < timestamps[i - 1]:
            return {
                "passed": False,
                "reason": f"Events not in chronological order at index {i}",
                "reason_code": "CHRONOLOGY_VIOLATION",
            }
    return {"passed": True, "reason": None, "reason_code": None}


def _check_inter_event_gaps(
    campaign: Campaign,
    config: GatekeeperConfig,
) -> dict[str, Any]:
    """Check inter-event gaps are within allowed bounds."""
    timestamps = [event.timestamp for event in campaign.events]
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if gap > config.max_inter_event_gap_seconds:
            return {
                "passed": False,
                "reason": (
                    f"Inter-event gap at index {i} is "
                    f"{gap:.0f}s, max is {config.max_inter_event_gap_seconds:.0f}s"
                ),
                "reason_code": "INTER_EVENT_GAP_TOO_LONG",
            }
        if gap < config.min_inter_event_gap_seconds:
            return {
                "passed": False,
                "reason": (
                    f"Inter-event gap at index {i} is "
                    f"{gap:.0f}s, min is {config.min_inter_event_gap_seconds:.0f}s"
                ),
                "reason_code": "INTER_EVENT_GAP_TOO_SHORT",
            }
    return {"passed": True, "reason": None, "reason_code": None}


def _check_amount_bounds(
    campaign: Campaign,
    config: GatekeeperConfig,
) -> dict[str, Any]:
    """Check that payment event amounts are within bounds."""
    for event in campaign.events:
        if event.type in ("payment", "ach_transfer", "transfer", "refund"):
            amount = event.params.get("amount")
            if isinstance(amount, dict):
                min_amt = amount.get("min", 0)
                max_amt = amount.get("max", float("inf"))
            elif isinstance(amount, (int, float)):
                min_amt = max_amt = amount
            else:
                continue

            if min_amt < config.min_amount or max_amt > config.max_amount:
                return {
                    "passed": False,
                    "reason": (
                        f"Amount {min_amt}-{max_amt} outside bounds "
                        f"[{config.min_amount}, {config.max_amount}]"
                    ),
                    "reason_code": "AMOUNT_OUT_OF_RANGE",
                }
    return {"passed": True, "reason": None, "reason_code": None}


def _check_actor_role_consistency(
    campaign: Campaign,
) -> dict[str, Any]:
    """Check that each actor role is consistently bound to the same entity."""
    actor_entities: dict[str, set[str]] = {}
    for event in campaign.events:
        for role, entity_id in event.actors.items():
            if role not in actor_entities:
                actor_entities[role] = set()
            actor_entities[role].add(entity_id)

    for role, entities in actor_entities.items():
        # In a well-formed campaign, each role should bind to a consistent entity
        # (or have a small set if that's intentional, but consistency is preferred)
        if len(entities) > 1:
            return {
                "passed": False,
                "reason": f"Role '{role}' binds to {len(entities)} different entities: {sorted(entities)}",
                "reason_code": "INCONSISTENT_ACTOR_ROLES",
            }
    return {"passed": True, "reason": None, "reason_code": None}


def _check_minimum_payload_fields(
    campaign: Campaign,
    archetype: Archetype | None = None,
) -> dict[str, Any]:
    """Verify each event has the minimum payload fields expected for its type.

    Payment-like events should have an 'amount' parameter.
    Other event types only need to be present (the Event object always has
    type/actors/params/metadata — we only verify the contents of `params`).
    """
    payment_like_types = {"payment", "ach_transfer", "transfer", "refund", "payout"}

    for event in campaign.events:
        # Every event must have a non-empty actors mapping
        if not event.actors:
            return {
                "passed": False,
                "reason": f"Event '{event.type}' has no actors bound",
                "reason_code": "MISSING_PAYLOAD_FIELDS",
            }
        # Payment-like events must include an amount
        if event.type in payment_like_types:
            if "amount" not in event.params:
                return {
                    "passed": False,
                    "reason": f"Event '{event.type}' missing 'amount' in params",
                    "reason_code": "MISSING_PAYLOAD_FIELDS",
                }
    return {"passed": True, "reason": None, "reason_code": None}


def _check_archetype_consistency(
    campaign: Campaign,
    config: GatekeeperConfig,
    archetype: Archetype | None = None,
) -> dict[str, Any]:
    """Check that campaign events are consistent with the declared archetype."""
    if not config.strict_archetype_match or not archetype:
        return {"passed": True, "reason": None, "reason_code": None}

    # Simple heuristic: check that event types used in the campaign
    # are among those defined in the archetype's event sequences
    archetype_event_types = set()
    for archetype_archetype in archetype.event_sequences:
        for step in archetype_archetype.steps:
            archetype_event_types.add(step.type)

    campaign_event_types = {event.type for event in campaign.events}

    unknown_types = campaign_event_types - archetype_event_types
    if unknown_types:
        return {
            "passed": False,
            "reason": (
                f"Campaign uses event types not in archetype: "
                f"{sorted(unknown_types)}"
            ),
            "reason_code": "ARCHETYPE_INCONSISTENT",
        }
    return {"passed": True, "reason": None, "reason_code": None}


# ---------------------------------------------------------------------------
# Main check orchestrator
# ---------------------------------------------------------------------------


def run_all_checks(
    campaign: Campaign,
    config: GatekeeperConfig | None = None,
    archetype: Archetype | None = None,
) -> GatekeeperResult:
    """Run all Gatekeeper checks on a campaign.

    Returns a GatekeeperResult with all checks and the overall verdict.
    """
    config = config or GatekeeperConfig()

    checks = [
        _check_min_max_events(campaign, config),
        _check_event_chronology(campaign),
        _check_inter_event_gaps(campaign, config),
        _check_amount_bounds(campaign, config),
        _check_actor_role_consistency(campaign),
        _check_minimum_payload_fields(campaign),
        _check_archetype_consistency(campaign, config, archetype),
    ]

    # Collect failures
    failures = [c for c in checks if not c["passed"]]

    if not failures:
        return GatekeeperResult(valid=True)

    # Pick the most severe/reason-code-first failure
    reason_codes = [f["reason_code"] for f in failures]
    reason_codes.sort()  # deterministic ordering

    # Use the first failure as the primary reason
    primary = failures[0]

    # Build invalid components list
    invalid_components = []
    for f in failures:
        invalid_components.append(
            {"reason_code": f["reason_code"], "reason": f["reason"]}
        )

    return GatekeeperResult(
        valid=False,
        reason=primary["reason"],
        reason_code=primary["reason_code"],
        invalid_components=invalid_components,
    )


def check_campaign(
    campaign: Campaign,
    config: GatekeeperConfig | None = None,
    archetype_id: str | None = None,
    taxonomy: type | None = None,
) -> GatekeeperResult:
    """Convenience: check a campaign against an archetype from taxonomy."""
    config = config or GatekeeperConfig()
    archetype = None
    if archetype_id and taxonomy:
        archetype = next(
            (a for a in taxonomy.archetypes if a.id == archetype_id),
            None,
        )
    return run_all_checks(campaign, config, archetype)