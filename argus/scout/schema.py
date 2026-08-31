"""Scout schema — Pydantic models for attack archetypes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

HERE = Path(__file__).parent
DEFAULT_TAXONOMY_PATH = HERE / "data" / "taxonomy.json"


CHANNELS = frozenset(
    {
        "online",
        "pos",
        "mobile",
        "call_center",
        "api",
        "atm",
        "in_person",
    }
)

RAILS = frozenset(
    {
        "card",
        "ach",
        "wire",
        "rtp",
        "crypto",
        "prepaid",
        "checks",
    }
)

EVENT_TYPES = frozenset(
    {
        "payment",
        "bank_transfer",
        "transfer",
        "ach_transfer",
        "account_open",
        "device_bind",
        "login",
        "password_reset",
        "address_change",
        "refund",
        "chargeback",
        "kyc",
        "beneficiary_add",
        "payout",
        "dispute",
        "goods_received",
        "service_used",
        "card_present",
        "card_not_present",
    }
)

ACTOR_ROLES = frozenset(
    {
        "customer",
        "device",
        "merchant",
        "beneficiary",
        "acquirer",
        "card",
        "account",
    }
)


class EventSpec(BaseModel):
    """One step in an event sequence template."""

    type: str = Field(..., description="Event type (e.g. payment, payout)")

    actors: list[str] = Field(
        default_factory=list,
        description="Roles that must be bound before this step",
    )

    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Fixed parameters for this event type",
    )

    conditions: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "List of conditions. Each: {event_idx: int, field: str, op: str, value: Any}. "
            "field paths are dot-separated: e.g. 'events.0.type'. "
            "ops: 'eq', 'ne', 'gt', 'lt', 'ge', 'le', 'exists', 'not_exists'. "
            "Condition is true when ALL entries match."
        ),
    )

    @field_validator("type")
    @classmethod
    def type_valid(cls, v: str) -> str:
        if v not in EVENT_TYPES:
            raise ValueError(
                f"Unknown event type: {v!r}. Known: {sorted(EVENT_TYPES)}"
            )
        return v

    @field_validator("actors", mode="after")
    @classmethod
    def actors_valid(cls, v: list[str]) -> list[str]:
        for r in v:
            if r not in ACTOR_ROLES:
                raise ValueError(
                    f"Unknown actor role: {r!r}. Known: {sorted(ACTOR_ROLES)}"
                )

        if len(v) != len(set(v)):
            raise ValueError(f"Duplicate actor roles: {v}")

        return v


class EventSequence(BaseModel):
    """Ordered list of event specs forming one attack variant."""

    name: str = Field(..., description="Human-readable name of this variant")

    description: str = Field(
        default="",
        description="Plain-language description",
    )

    steps: list[EventSpec] = Field(..., min_length=1)

    @model_validator(mode="after")
    def check_event_refs(self) -> "EventSequence":
        """All referenced event_idx values must be < the referencing step index."""

        for step_idx, step in enumerate(self.steps):
            for cond in step.conditions:
                ref_idx = cond.get("event_idx", step_idx)

                if ref_idx >= step_idx:
                    raise ValueError(
                        f"Step {step_idx} ({step.type!r}) has a condition "
                        f"referencing event_idx={ref_idx} which is not less "
                        f"than step index. Events can only reference earlier steps."
                    )

        return self


class Archetype(BaseModel):
    """A fraud attack archetype — a safe, structured scenario vocabulary entry."""

    id: str = Field(..., pattern=r"^[a-z0-9_]+$")

    name: str = Field(
        ...,
        min_length=3,
        max_length=80,
    )

    channel: str = Field(
        ...,
        description="Primary delivery channel",
    )

    rail: str = Field(
        ...,
        description="Payment rail used",
    )

    objective: str = Field(
        ...,
        min_length=10,
        max_length=500,
    )

    description: str = Field(
        default="",
        description="Detailed plain-language description of the attack pattern",
    )

    mitigations: list[str] = Field(
        default_factory=list,
        min_length=1,
        description="Known defensive countermeasures",
    )

    event_sequences: list[EventSequence] = Field(
        ...,
        min_length=1,
        description="One or more variants of the attack",
    )

    genai_enabled: bool = Field(
        default=False,
        description=(
            "Whether Oracle may assist with drafting the plain-language "
            "description for human review. Oracle is never used to "
            "generate attack instructions."
        ),
    )

    @field_validator("channel")
    @classmethod
    def channel_valid(cls, v: str) -> str:
        if v not in CHANNELS:
            raise ValueError(
                f"Unknown channel: {v!r}. Known: {sorted(CHANNELS)}"
            )
        return v

    @field_validator("rail")
    @classmethod
    def rail_valid(cls, v: str) -> str:
        if v not in RAILS:
            raise ValueError(
                f"Unknown rail: {v!r}. Known: {sorted(RAILS)}"
            )
        return v

    @field_validator("mitigations", mode="after")
    @classmethod
    def mitigations_unique(cls, v: list[str]) -> list[str]:
        seen = set()

        for m in v:
            if m in seen:
                raise ValueError(f"Duplicate mitigation: {m!r}")

            seen.add(m)

        return v


class Taxonomy(BaseModel):
    """Root model for a taxonomy JSON file."""

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+$",
    )

    generated_at: str = Field(
        ...,
        description="ISO-8601 timestamp",
    )

    archetypes: list[Archetype] = Field(
        ...,
        min_length=1,
    )

    @field_validator("archetypes", mode="after")
    @classmethod
    def unique_ids(cls, v: list[Archetype]) -> list[Archetype]:
        ids = [a.id for a in v]

        if len(ids) != len(set(ids)):
            dupes = [x for x in ids if ids.count(x) > 1]
            raise ValueError(
                f"Duplicate archetype ids: {sorted(set(dupes))}"
            )

        return v


def load_taxonomy(path: Path | str | None = None) -> Taxonomy:
    """Load and validate a taxonomy JSON file."""

    p = Path(path) if path else DEFAULT_TAXONOMY_PATH

    if not p.exists():
        raise FileNotFoundError(
            f"Taxonomy not found at {p}. "
            "Did you run Phase 1 (Scout) to generate the taxonomy file?"
        )

    data = json.loads(
        p.read_text(encoding="utf-8")
    )

    return Taxonomy.model_validate(data)


def validate_taxonomy(path: Path | str | None = None) -> list[str]:
    """Return list of warning strings for a taxonomy (errors raise)."""

    taxonomy = load_taxonomy(path)

    warnings: list[str] = []

    ids = {a.id for a in taxonomy.archetypes}

    if len(ids) != len(taxonomy.archetypes):
        dupes = {
            x
            for x in ids
            if list(a.id for a in taxonomy.archetypes).count(x) > 1
        }

        raise ValueError(
            f"Duplicate archetype ids: {sorted(dupes)}"
        )

    return warnings