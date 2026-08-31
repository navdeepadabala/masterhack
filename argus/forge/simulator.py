"""Forge simulator — deterministic synthetic payment-network generator."""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from argus.forge.config import ForgeConfig, ForgeParams
from argus.scout.schema import Archetype, EventSequence, EventSpec
from argus.scout.taxonomy import TAXONOMY


# ---------------------------------------------------------------------------
# Legitimate event sequences (normal customer behavior — not attacks)
# ---------------------------------------------------------------------------

# Predefined normal customer flows that represent legitimate activity.
# These use the same EVENT_TYPES vocabulary but with non-fraudulent patterns.
LEGITIMATE_SEQUENCES = [
    # Normal shopping — account open, bind device, occasional purchases
    {
        "name": "normal_shopping",
        "description": "Regular customer making purchases",
        "steps": [
            {"type": "account_open", "actors": ["customer", "device"], "params": {}},
            {"type": "device_bind", "actors": ["customer", "device"], "params": {}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 10.0, "max": 100.0}}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 5.0, "max": 80.0}}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 15.0, "max": 200.0}}},
        ],
    },
    # Online subscription — recurring small payments
    {
        "name": "online_subscription",
        "description": "Customer with recurring subscriptions",
        "steps": [
            {"type": "account_open", "actors": ["customer", "device"], "params": {}},
            {"type": "device_bind", "actors": ["customer", "device"], "params": {}},
            {"type": "login", "actors": ["customer", "device"], "params": {"username": "customer", "password": "valid"}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 5.0, "max": 25.0}, "recurring": True}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 10.0, "max": 50.0}, "recurring": True}},
            {"type": "service_used", "actors": ["customer", "merchant"], "params": {"duration": {"min": 1, "max": 30}}},
        ],
    },
    # Bill payment via ACH — normal utility payments
    {
        "name": "bill_payment",
        "description": "Customer paying bills through ACH",
        "steps": [
            {"type": "account_open", "actors": ["customer", "device"], "params": {}},
            {"type": "device_bind", "actors": ["customer", "device"], "params": {}},
            {"type": "login", "actors": ["customer", "device"], "params": {"username": "customer", "password": "valid"}},
            {"type": "ach_transfer", "actors": ["customer", "beneficiary"], "params": {"amount": {"min": 50.0, "max": 300.0}}},
            {"type": "ach_transfer", "actors": ["customer", "beneficiary"], "params": {"amount": {"min": 30.0, "max": 200.0}}},
        ],
    },
    # Mixed activity — in-store and online
    {
        "name": "mixed_activity",
        "description": "Customer with mixed POS and online activity",
        "steps": [
            {"type": "account_open", "actors": ["customer", "device"], "params": {}},
            {"type": "device_bind", "actors": ["customer", "device"], "params": {}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 8.0, "max": 60.0}}},
            {"type": "login", "actors": ["customer", "device"], "params": {"username": "customer", "password": "valid"}},
            {"type": "payment", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 20.0, "max": 150.0}}},
            {"type": "refund", "actors": ["customer", "card", "merchant"], "params": {"amount": {"min": 5.0, "max": 30.0}}},
        ],
    },
    # Transfer to own account
    {
        "name": "own_transfer",
        "description": "Customer transferring between own accounts",
        "steps": [
            {"type": "account_open", "actors": ["customer", "device"], "params": {}},
            {"type": "device_bind", "actors": ["customer", "device"], "params": {}},
            {"type": "login", "actors": ["customer", "device"], "params": {"username": "customer", "password": "valid"}},
            {"type": "transfer", "actors": ["customer", "beneficiary"], "params": {"amount": {"min": 100.0, "max": 1000.0}}},
        ],
    },
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entity:
    """A persistent entity in the payment network."""

    id: str
    type: str  # customer, device, merchant, beneficiary
    attributes: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)
    created_at: datetime = field(
        default_factory=lambda: datetime(2026, 1, 1, 0, 0, 0),
        hash=False,
        compare=False,
    )

    @property
    def key(self) -> tuple[str, str]:
        return (self.type, self.id)


@dataclass(frozen=True)
class Event:
    """One step in a campaign."""

    type: str
    timestamp: datetime
    actors: dict[str, str] = field(default_factory=dict, hash=False, compare=False)  # role -> entity_id
    params: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)
    metadata: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)


@dataclass(frozen=True)
class Campaign:
    """A synthetic payment network campaign.

    Attributes:
        id: Unique campaign ID
        seed: Random seed used
        archetype_id: Which attack archetype (or None for legitimate)
        variant_name: Which variant within archetype (or legitimate sequence name)
        label: 0 for legitimate, 1 for attack/fraud
        start_time: When the campaign begins
        events: Ordered sequence of events
        entities: Entity graph used by this campaign
        features: Extracted features for ML models
    """

    id: str
    seed: int
    archetype_id: str | None  # None for legitimate
    variant_name: str
    label: int = 0  # 0=legitimate, 1=attack
    start_time: datetime = field(default_factory=lambda: datetime(2026, 1, 1, 0, 0, 0))
    events: tuple[Event, ...] = field(default_factory=tuple)
    entities: frozenset[Entity] = field(default_factory=frozenset)
    features: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to serializable dict."""
        return {
            "id": self.id,
            "seed": self.seed,
            "archetype_id": self.archetype_id,
            "variant_name": self.variant_name,
            "label": self.label,
            "start_time": self.start_time.isoformat(),
            "events": [
                {
                    "type": e.type,
                    "timestamp": e.timestamp.isoformat(),
                    "actors": dict(e.actors),
                    "params": dict(e.params),
                    "metadata": dict(e.metadata),
                }
                for e in self.events
            ],
            "entities": [
                {
                    "id": ent.id,
                    "type": ent.type,
                    "attributes": dict(ent.attributes),
                    "created_at": ent.created_at.isoformat(),
                }
                for ent in self.entities
            ],
            "features": dict(self.features),
        }


# ---------------------------------------------------------------------------
# Core simulator
# ---------------------------------------------------------------------------


class CampaignGenerator:
    """Deterministic campaign generator."""

    def __init__(self, config: ForgeConfig | None = None):
        self.config = config or ForgeConfig()
        self.rng = random.Random(self.config.rng_seed)

    def reset(self, seed: int) -> None:
        """Reset RNG with new seed."""
        self.rng = random.Random(seed)

    def generate_campaign(
        self,
        params: ForgeParams,
        taxonomy: type[TAXONOMY] = TAXONOMY,
    ) -> Campaign:
        """Generate a deterministic campaign from archetype+variant."""
        self.reset(params.seed)
        config = params.resolve_config()

        # Look up archetype and variant
        archetype = next(
            (a for a in taxonomy.archetypes if a.id == params.archetype_id),
            None,
        )
        if not archetype:
            raise ValueError(f"Archetype {params.archetype_id} not found")

        variant = next(
            (v for v in archetype.event_sequences if v.name == params.variant_name),
            None,
        )
        if not variant:
            raise ValueError(
                f"Variant {params.variant_name} not found in archetype {params.archetype_id}"
            )

        # Generate campaign ID (deterministic hash)
        campaign_id = self._generate_campaign_id(params.seed, params.archetype_id, params.variant_name)

        # Build entity graph
        entity_graph = self._build_entity_graph(config)

        # Base timestamp anchored deterministically
        start_time = datetime(2026, 1, 1, 0, 0, 0)

        # Generate events
        events = self._generate_events(variant, entity_graph, config, base_time=start_time)

        # Compute features
        features = self._compute_features(events, entity_graph)

        return Campaign(
            id=campaign_id,
            seed=params.seed,
            archetype_id=params.archetype_id,
            variant_name=params.variant_name,
            label=1,  # attack campaigns
            start_time=start_time,
            events=tuple(events),
            entities=frozenset(entity_graph.values()),
            features=features,
        )

    def generate_legitimate_campaign(self, seed: int, sequence_name: str | None = None) -> Campaign:
        """Generate a deterministic legitimate (non-attack) campaign.

        Uses predefined LEGITIMATE_SEQUENCES to construct normal customer behavior.
        """
        self.reset(seed)
        config = ForgeConfig(rng_seed=seed)

        # Pick a legitimate sequence (deterministic from seed)
        if sequence_name is None:
            idx = seed % len(LEGITIMATE_SEQUENCES)
            sequence_name = LEGITIMATE_SEQUENCES[idx]["name"]

        seq_def = next(
            (s for s in LEGITIMATE_SEQUENCES if s["name"] == sequence_name),
            LEGITIMATE_SEQUENCES[0],
        )

        # Build entity graph
        entity_graph = self._build_entity_graph(config)

        # Build a pseudo-EventSequence from the dict
        steps = [
            EventSpec(
                type=s["type"],
                actors=s["actors"],
                params=s.get("params", {}),
                conditions=[],
            )
            for s in seq_def["steps"]
        ]
        variant = EventSequence(name=sequence_name, description=seq_def["description"], steps=steps)

        # Generate campaign ID
        campaign_id = self._generate_campaign_id_legit(seed, sequence_name)

        # Generate events
        start_time = datetime(2026, 1, 1, 0, 0, 0)
        events = self._generate_events(variant, entity_graph, config, base_time=start_time)
        features = self._compute_features(events, entity_graph)

        return Campaign(
            id=campaign_id,
            seed=seed,
            archetype_id=None,
            variant_name=sequence_name,
            label=0,  # legitimate
            start_time=start_time,
            events=tuple(events),
            entities=frozenset(entity_graph.values()),
            features=features,
        )

    def generate_legitimate_pool(
        self,
        n_campaigns: int,
        base_seed: int = 0,
        config: ForgeConfig | None = None,
        taxonomy: type[TAXONOMY] = TAXONOMY,
    ) -> list[Campaign]:
        """Generate a pool of legitimate (non-attack) campaigns.

        Each campaign is a normal customer activity flow (not an attack).
        """
        campaigns = []
        for i in range(n_campaigns):
            seed = base_seed + i
            campaign = self.generate_legitimate_campaign(seed=seed)
            campaigns.append(campaign)
        return campaigns

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _generate_campaign_id(self, seed: int, archetype_id: str, variant_name: str) -> str:
        """Generate deterministic campaign ID."""
        data = f"{seed}:{archetype_id}:{variant_name}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:16]

    def _generate_campaign_id_legit(self, seed: int, sequence_name: str) -> str:
        """Generate deterministic campaign ID for a legitimate sequence."""
        data = f"legit:{seed}:{sequence_name}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:16]

    def _build_entity_graph(self, config: ForgeConfig) -> dict[tuple[str, str], Entity]:
        """Build persistent entity graph for a campaign."""
        entities = {}
        rng = self.rng

        # Customers
        for i in range(config.n_customers):
            cust_id = f"cust_{i:04d}"
            entities[("customer", cust_id)] = Entity(
                id=cust_id,
                type="customer",
                attributes={
                    "age": rng.randint(18, 80),
                    "country": rng.choice(["US", "CA", "UK", "DE", "FR"]),
                    "risk_score": round(rng.uniform(0.0, 1.0), 3),
                },
            )

        # Devices (1-3 per customer)
        device_idx = 0
        for cust_key, cust in [e for e in entities.items() if e[0][0] == "customer"]:
            for _ in range(rng.randint(1, 3)):
                dev_id = f"dev_{device_idx:04d}"
                entities[("device", dev_id)] = Entity(
                    id=dev_id,
                    type="device",
                    attributes={
                        "fingerprint": f"fp_{dev_id}",
                        "os": rng.choice(["iOS", "Android", "Web"]),
                        "is_emulator": rng.random() < 0.05,  # 5% emulators
                    },
                )
                device_idx += 1

        # Merchants
        for i in range(config.n_merchants):
            merc_id = f"merc_{i:04d}"
            entities[("merchant", merc_id)] = Entity(
                id=merc_id,
                type="merchant",
                attributes={
                    "category": rng.choice(["retail", "food", "travel", "digital", "services"]),
                    "country": rng.choice(["US", "CA", "UK", "DE", "FR"]),
                    "risk_score": round(rng.uniform(0.0, 1.0), 3),
                },
            )

        # Beneficiaries (for ACH/payouts)
        for i in range(config.n_beneficiaries):
            bene_id = f"bene_{i:04d}"
            entities[("beneficiary", bene_id)] = Entity(
                id=bene_id,
                type="beneficiary",
                attributes={
                    "account_type": rng.choice(["checking", "savings", "business"]),
                    "country": rng.choice(["US", "CA", "UK", "DE", "FR"]),
                },
            )

        # Cards (linked to customer accounts)
        for i in range(config.n_cards):
            card_id = f"card_{i:04d}"
            # Link to a customer
            owner_cust_idx = i % config.n_customers
            owner_cust_id = f"cust_{owner_cust_idx:04d}"
            entities[("card", card_id)] = Entity(
                id=card_id,
                type="card",
                attributes={
                    "last_four": f"{rng.randint(1000, 9999)}",
                    "card_type": rng.choice(["credit", "debit", "prepaid"]),
                    "country": rng.choice(["US", "CA", "UK", "DE", "FR"]),
                    "owner_cust_id": owner_cust_id,
                },
            )

        # Accounts (bank accounts for ACH/wire)
        for i in range(config.n_accounts):
            acct_id = f"acct_{i:04d}"
            # Link to a customer
            owner_cust_idx = i % config.n_customers
            owner_cust_id = f"cust_{owner_cust_idx:04d}"
            entities[("account", acct_id)] = Entity(
                id=acct_id,
                type="account",
                attributes={
                    "account_type": rng.choice(["checking", "savings", "business"]),
                    "country": rng.choice(["US", "CA", "UK", "DE", "FR"]),
                    "owner_cust_id": owner_cust_id,
                    "routing_number": f"{rng.randint(100000000, 999999999)}",
                },
            )

        return entities

    def _generate_events(
        self,
        variant: EventSequence,
        entity_graph: dict[tuple[str, str], Entity],
        config: ForgeConfig,
        base_time: datetime | None = None,
    ) -> list[Event]:
        """Generate ordered events for a campaign variant."""
        events = []
        timestamp = base_time or datetime(2026, 1, 1, 0, 0, 0)
        entity_bindings: dict[str, str] = {}  # role -> entity_id used for this role

        for step_idx, step in enumerate(variant.steps):
            # Apply time gap
            gap_noise = 1.0 + (self.rng.random() - 0.5) * 2 * config.gap_noise_factor
            gap = config.base_inter_event_gap_seconds * gap_noise
            timestamp += timedelta(seconds=gap)

            # Bind actors (assign entities to roles)
            actors = {}
            for role in step.actors:
                if role in entity_bindings:
                    # Reuse previously bound entity for this role
                    actors[role] = entity_bindings[role]
                else:
                    # Bind new entity for this role
                    entity_id = self._bind_entity(role, entity_graph, entity_bindings)
                    actors[role] = entity_id
                    entity_bindings[role] = entity_id

            # Generate parameters
            params = self._generate_event_params(step, config)

            # Create event
            event = Event(
                type=step.type,
                timestamp=timestamp,
                actors=actors,
                params=params,
                metadata={
                    "step_index": step_idx,
                    "variant_name": variant.name,
                    "archetype_id": getattr(variant, "archetype_id", "unknown"),
                },
            )
            events.append(event)

        return events

    def _bind_entity(
        self,
        role: str,
        entity_graph: dict[tuple[str, str], Entity],
        current_bindings: dict[str, str],
    ) -> str:
        """Bind an entity to a role, preferring unbound entities if possible."""
        rng = self.rng

        # Get all entities of the required type
        candidates = [
            (key, ent) for key, ent in entity_graph.items() if key[0] == role
        ]

        if not candidates:
            raise ValueError(f"No entities of type {role} available")

        # Prefer entities not currently bound to any role (for first use)
        unbound = [
            (key, ent)
            for key, ent in candidates
            if ent.id not in current_bindings.values()
        ]

        pool = unbound if unbound else candidates
        key, entity = rng.choice(pool)
        return entity.id

    def _generate_event_params(
        self,
        step: EventSpec,
        config: ForgeConfig,
    ) -> dict[str, Any]:
        """Generate parameters for an event step."""
        params = dict(step.params)  # Start with fixed params

        # Add noise to numeric parameters
        for key, value in list(params.items()):
            if isinstance(value, dict) and "min" in value and "max" in value:
                # Range parameter
                min_val = value["min"]
                max_val = value["max"]
                if isinstance(min_val, (int, float)) and isinstance(max_val, (int, float)):
                    noise = 1.0 + (self.rng.random() - 0.5) * 2 * config.amount_noise_factor
                    range_width = max_val - min_val
                    center = (min_val + max_val) / 2
                    noisy_center = center * noise
                    half_width = range_width / 2
                    new_min = max(0, noisy_center - half_width)
                    new_max = noisy_center + half_width
                    params[key] = {"min": new_min, "max": new_max}
            elif isinstance(value, (int, float)):
                # Scalar numeric parameter
                noise = 1.0 + (self.rng.random() - 0.5) * 2 * config.amount_noise_factor
                params[key] = value * noise

        return params

    def _compute_features(
        self,
        events: list[Event],
        entity_graph: dict[tuple[str, str], Entity],
    ) -> dict[str, Any]:
        """Compute campaign-level features for Sentinel."""
        if not events:
            return {}

        # Timing features
        timestamps = [e.timestamp for e in events]
        gaps = [
            (timestamps[i + 1] - timestamps[i]).total_seconds()
            for i in range(len(timestamps) - 1)
        ]

        # Amount features (for payment-like events)
        payment_events = [e for e in events if e.type in ("payment", "ach_transfer", "transfer", "refund")]
        amounts = []
        for e in payment_events:
            amount = e.params.get("amount")
            if isinstance(amount, dict) and "min" in amount and "max" in amount:
                # Use midpoint of range
                amounts.append((amount["min"] + amount["max"]) / 2)
            elif isinstance(amount, (int, float)):
                amounts.append(amount)

        # Entity reuse features
        entity_usage: dict[str, int] = defaultdict(int)
        for e in events:
            for role, entity_id in e.actors.items():
                entity_usage[entity_id] += 1

        # Velocity features
        time_span = (timestamps[-1] - timestamps[0]).total_seconds() if len(timestamps) > 1 else 0
        events_per_hour = len(events) / (time_span / 3600) if time_span > 0 else len(events)

        return {
            "n_events": len(events),
            "time_span_seconds": time_span,
            "avg_inter_event_gap": sum(gaps) / len(gaps) if gaps else 0,
            "gap_std": (
                sum((g - (sum(gaps) / len(gaps))) ** 2 for g in gaps) / len(gaps)
                if gaps
                else 0
            ) ** 0.5,
            "n_payments": len(payment_events),
            "total_amount": sum(amounts) if amounts else 0,
            "avg_amount": sum(amounts) / len(amounts) if amounts else 0,
            "amount_std": (
                sum((a - (sum(amounts) / len(amounts))) ** 2 for a in amounts) / len(amounts)
                if amounts
                else 0
            ) ** 0.5,
            "unique_entities": len(set(entity_usage.keys())),
            "entity_reuse_ratio": sum(c > 1 for c in entity_usage.values()) / len(entity_usage)
            if entity_usage
            else 0,
            "max_entity_usage": max(entity_usage.values()) if entity_usage else 0,
            "events_per_hour": events_per_hour,
            "first_event_type": events[0].type if events else None,
            "last_event_type": events[-1].type if events else None,
        }

    def _pick_archetype(self, taxonomy: type[TAXONOMY]):
        """Pick an archetype for legitimate pool generation."""
        archetypes = list(taxonomy.archetypes)
        if not self.config.archetype_weights:
            return self.rng.choice(archetypes)

        # Weighted selection
        weights = [
            self.config.archetype_weights.get(a.id, 1.0) for a in archetypes
        ]
        total = sum(weights)
        r = self.rng.random() * total
        upto = 0
        for archetype, weight in zip(archetypes, weights):
            if upto + weight >= r:
                return archetype
            upto += weight
        return archetypes[-1]

    def _pick_variant(self, archetype: Archetype) -> EventSequence:
        """Pick a variant from an archetype."""
        return self.rng.choice(archetype.event_sequences)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def generate_campaign(params: ForgeParams) -> Campaign:
    """Generate a single campaign."""
    generator = CampaignGenerator(params.config)
    return generator.generate_campaign(params)


def generate_legitimate_pool(
    n_campaigns: int,
    base_seed: int = 0,
    config: ForgeConfig | None = None,
) -> list[Campaign]:
    """Generate a pool of legitimate campaigns."""
    generator = CampaignGenerator(config)
    return generator.generate_legitimate_pool(n_campaigns, base_seed)