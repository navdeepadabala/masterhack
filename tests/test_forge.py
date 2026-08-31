"""Tests for Forge (Phase 2) — determinism and campaign generation."""
from __future__ import annotations

import json
import pytest

from argus.scout.taxonomy import TAXONOMY
from argus.forge.simulator import CampaignGenerator, Campaign, ForgeParams, ForgeConfig
from argus.forge.config import ForgeParams


class TestDeterminism:
    """Same seed + same archetype => byte-identical campaign output."""

    def test_same_seed_same_campaign(self):
        cfg = ForgeConfig(rng_seed=12345)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=12345, archetype_id="card_craftering", variant_name="test_then_bust")
        c1 = gen.generate_campaign(params)
        c2 = gen.generate_campaign(params)
        assert c1.id == c2.id
        assert c1.events == c2.events

    def test_different_seed_different_campaign(self):
        cfg = ForgeConfig(rng_seed=12345)
        gen = CampaignGenerator(cfg)
        params1 = ForgeParams(seed=11111, archetype_id="card_craftering", variant_name="test_then_bust")
        params2 = ForgeParams(seed=22222, archetype_id="card_craftering", variant_name="test_then_bust")
        c1 = gen.generate_campaign(params1)
        c2 = gen.generate_campaign(params2)
        assert c1.id != c2.id

    def test_deterministic_with_taxonomy(self):
        cfg = ForgeConfig(rng_seed=99999)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=99999, archetype_id="account_takeover", variant_name="phishing_then_transfer")
        c = gen.generate_campaign(params)
        assert c.archetype_id == "account_takeover"
        assert c.variant_name == "phishing_then_transfer"
        assert len(c.events) >= 1
        assert c.entities


class TestCampaignStructure:
    """Campaign structure validation."""

    def test_campaign_has_required_fields(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="test_then_bust")
        c = gen.generate_campaign(params)
        assert c.id
        assert c.seed == 42
        assert c.archetype_id == "card_craftering"
        assert c.variant_name == "test_then_bust"
        assert c.events
        assert c.entities
        assert c.features

    def test_campaign_to_dict_serializable(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="test_then_bust")
        c = gen.generate_campaign(params)
        d = c.to_dict()
        assert isinstance(d, dict)
        s = json.dumps(d)
        assert json.loads(s)  # roundtrip

    def test_events_are_ordered(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="multiple_small")
        c = gen.generate_campaign(params)
        timestamps = [e.timestamp for e in c.events]
        assert timestamps == sorted(timestamps), "Events must be in chronological order"

    def test_entities_persist_across_events(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="test_then_bust")
        c = gen.generate_campaign(params)
        # Check that entities are used across events (reuse)
        all_actor_ids = set()
        for e in c.events:
            all_actor_ids.update(e.actors.values())
        assert all_actor_ids.issubset({ent.id for ent in c.entities})

    def test_features_computed(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="test_then_bust")
        c = gen.generate_campaign(params)
        assert "n_events" in c.features
        assert c.features["n_events"] == len(c.events)
        assert "time_span_seconds" in c.features
        assert "unique_entities" in c.features


class TestLegitimatePool:
    """Legitimate (non-attack) campaign generation."""

    def test_legitimate_pool_size(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        pool = gen.generate_legitimate_pool(n_campaigns=10, base_seed=100)
        assert len(pool) == 10

    def test_legitimate_pool_deterministic(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        pool1 = gen.generate_legitimate_pool(n_campaigns=5, base_seed=200)
        gen2 = CampaignGenerator(cfg)
        pool2 = gen2.generate_legitimate_pool(n_campaigns=5, base_seed=200)
        assert [c.id for c in pool1] == [c.id for c in pool2]

    def test_legitimate_pool_uses_known_archetypes(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        pool = gen.generate_legitimate_pool(n_campaigns=20, base_seed=300)
        known_ids = {a.id for a in TAXONOMY.archetypes}
        for c in pool:
            assert c.archetype_id in known_ids, f"Unknown archetype {c.archetype_id}"


class TestEdgeCases:
    """Error handling."""

    def test_unknown_archetype_raises(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="nonexistent_archetype", variant_name="foo")
        with pytest.raises(ValueError, match="not found"):
            gen.generate_campaign(params)

    def test_unknown_variant_raises(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="nonexistent_variant")
        with pytest.raises(ValueError, match="not found"):
            gen.generate_campaign(params)
