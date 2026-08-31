"""Tests for Scout (Phase 1)."""
from __future__ import annotations

import pytest

from argus.scout.schema import (
    Taxonomy,
    Archetype,
    EventSequence,
    EventSpec,
    load_taxonomy,
    CHANNELS,
    RAILS,
    EVENT_TYPES,
    ACTOR_ROLES,
)


class TestSchemaValidation:
    """Schema safety tests."""

    def test_channels_known(self):
        assert "online" in CHANNELS
        assert "pos" in CHANNELS
        assert "mobile" in CHANNELS

    def test_rails_known(self):
        assert "card" in RAILS
        assert "ach" in RAILS
        assert "wire" in RAILS

    def test_event_types_known(self):
        assert "payment" in EVENT_TYPES
        assert "account_open" in EVENT_TYPES
        assert "beneficiary_add" in EVENT_TYPES

    def test_actor_roles_known(self):
        assert "customer" in ACTOR_ROLES
        assert "device" in ACTOR_ROLES
        assert "merchant" in ACTOR_ROLES

    def test_archetype_requires_valid_channel(self):
        with pytest.raises(ValueError, match="Unknown channel"):
            Archetype(
                id="test",
                name="Test Archetype",
                channel="not_a_channel",
                rail="card",
                objective="Test objective for validation",
                event_sequences=[],
            )

    def test_archetype_requires_valid_rail(self):
        with pytest.raises(ValueError, match="Unknown rail"):
            Archetype(
                id="test",
                name="Test Archetype",
                channel="online",
                rail="not_a_rail",
                objective="Test objective for validation",
                event_sequences=[],
            )

    def test_archetype_requires_min_objective_length(self):
        with pytest.raises(ValueError):
            Archetype(
                id="test",
                name="Test",
                channel="online",
                rail="card",
                objective="short",
                event_sequences=[],
            )

    def test_archetype_requires_unique_mitigations(self):
        with pytest.raises(ValueError, match="Duplicate mitigation"):
            Archetype(
                id="test",
                name="Test",
                channel="online",
                rail="card",
                objective="Test objective length must be sufficient",
                mitigations=["foo", "foo"],
                event_sequences=[],
            )

    def test_event_spec_requires_valid_type(self):
        with pytest.raises(ValueError, match="Unknown event type"):
            EventSpec(type="not_a_type")

    def test_event_spec_requires_valid_actors(self):
        with pytest.raises(ValueError, match="Unknown actor role"):
            EventSpec(type="payment", actors=["not_a_role"])

    def test_event_spec_no_duplicate_actors(self):
        with pytest.raises(ValueError, match="Duplicate actor roles"):
            EventSpec(type="payment", actors=["customer", "customer"])

    def test_event_sequence_requires_min_one_step(self):
        with pytest.raises(ValueError):
            EventSequence(name="test", steps=[])

    def test_taxonomy_requires_unique_archetype_ids(self):
        step = EventSpec(type="payment", actors=["customer"])
        seq = EventSequence(name="test_seq", steps=[step])
        arch = Archetype(
            id="dup_id",
            name="Test Archetype",
            channel="online",
            rail="card",
            objective="Test objective for unique IDs",
            mitigations=["test mitigation measure"],
            event_sequences=[seq],
        )
        with pytest.raises(ValueError, match="Duplicate archetype ids"):
            Taxonomy(
                version="1.0.0",
                generated_at="2026-01-01T00:00:00Z",
                archetypes=[arch, arch],
            )


class TestTaxonomyLoader:
    """Taxonomy loading and validation tests."""

    def test_load_taxonomy_returns_taxonomy(self):
        taxonomy = load_taxonomy()
        assert isinstance(taxonomy, Taxonomy)
        assert taxonomy.version.startswith("1.")
        assert len(taxonomy.archetypes) >= 8

    def test_archetypes_have_required_fields(self):
        taxonomy = load_taxonomy()
        for arch in taxonomy.archetypes:
            assert arch.id
            assert arch.name
            assert arch.channel in CHANNELS
            assert arch.rail in RAILS
            assert len(arch.objective) >= 10
            assert arch.event_sequences
            for variant in arch.event_sequences:
                assert variant.name
                assert variant.steps

    def test_archetypes_have_variants(self):
        taxonomy = load_taxonomy()
        for arch in taxonomy.archetypes:
            assert len(arch.event_sequences) >= 2, f"{arch.id} needs at least 2 variants"

    def test_event_sequence_step_event_idx_bounds(self):
        """No step may reference a future step in its conditions."""
        taxonomy = load_taxonomy()
        for arch in taxonomy.archetypes:
            for variant in arch.event_sequences:
                for step_idx, step in enumerate(variant.steps):
                    for cond in step.conditions:
                        ref_idx = cond.get("event_idx", step_idx)
                        assert ref_idx < step_idx, (
                            f"{arch.id}/{variant.name} step {step_idx} "
                            f"references event_idx={ref_idx} (not less than {step_idx})"
                        )

    def test_no_duplicate_archetype_ids(self):
        taxonomy = load_taxonomy()
        ids = [a.id for a in taxonomy.archetypes]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"

    def test_taxonomy_json_roundtrip(self):
        taxonomy = load_taxonomy()
        data = taxonomy.model_dump()
        rebuilt = Taxonomy.model_validate(data)
        assert rebuilt.version == taxonomy.version
        assert len(rebuilt.archetypes) == len(taxonomy.archetypes)
