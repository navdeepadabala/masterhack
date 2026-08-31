"""Tests for Gatekeeper (Phase 3) — validity/fidelity firewall."""
from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from argus.forge.simulator import Campaign, Event, Entity, CampaignGenerator
from argus.forge.config import ForgeConfig, ForgeParams
from argus.gatekeeper.checks import (
    run_all_checks,
    check_campaign,
    GatekeeperResult,
    _check_event_chronology,
    _check_amount_bounds,
    _check_min_max_events,
)
from argus.gatekeeper.config import GatekeeperConfig


def _make_campaign_with_events(events: list[Event]) -> Campaign:
    """Helper to build a minimal Campaign for testing."""
    return Campaign(
        id="test_campaign",
        seed=42,
        archetype_id="card_craftering",
        variant_name="test",
        start_time=datetime(2026, 1, 1, 0, 0, 0),
        events=tuple(events),
        entities=frozenset(),
        features={"n_events": len(events)},
    )


def _make_event(
    timestamp: datetime,
    event_type: str = "payment",
    amount: float | None = 100.0,
    actors: dict | None = None,
) -> Event:
    return Event(
        type=event_type,
        timestamp=timestamp,
        actors=actors or {"customer": "c1"},
        params={"amount": amount} if amount is not None else {},
        metadata={},
    )


class TestGatekeeperResult:
    def test_valid_result(self):
        r = GatekeeperResult(valid=True)
        assert r.valid
        assert r.reason is None
        assert r.reason_code is None

    def test_invalid_result_has_reason(self):
        r = GatekeeperResult(
            valid=False,
            reason="Campaign has 0 events, minimum is 1",
            reason_code="EVENT_COUNT_LOW",
        )
        assert not r.valid
        assert r.reason is not None
        assert r.reason_code == "EVENT_COUNT_LOW"

    def test_to_dict(self):
        r = GatekeeperResult(
            valid=False,
            reason="test",
            reason_code="TEST",
            invalid_components=[{"reason_code": "TEST", "reason": "test"}],
        )
        d = r.to_dict()
        assert d["valid"] is False
        assert d["reason_code"] == "TEST"
        assert len(d["invalid_components"]) == 1


class TestChronologyCheck:
    def test_chronological_events_pass(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        t1 = t0 + timedelta(seconds=10)
        t2 = t1 + timedelta(seconds=10)
        events = [_make_event(t0), _make_event(t1), _make_event(t2)]
        c = _make_campaign_with_events(events)
        result = _check_event_chronology(c)
        assert result["passed"]

    def test_reverse_chronology_fails(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        t1 = t0 - timedelta(seconds=10)  # before t0
        events = [_make_event(t0), _make_event(t1)]
        c = _make_campaign_with_events(events)
        result = _check_event_chronology(c)
        assert not result["passed"]
        assert result["reason_code"] == "CHRONOLOGY_VIOLATION"


class TestAmountBoundsCheck:
    def test_amount_within_bounds_passes(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        events = [_make_event(t0, amount=500.0)]
        c = _make_campaign_with_events(events)
        cfg = GatekeeperConfig(min_amount=0.01, max_amount=50000.0)
        result = _check_amount_bounds(c, cfg)
        assert result["passed"]

    def test_amount_below_min_fails(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        events = [_make_event(t0, amount=0.001)]
        c = _make_campaign_with_events(events)
        cfg = GatekeeperConfig(min_amount=1.0, max_amount=50000.0)
        result = _check_amount_bounds(c, cfg)
        assert not result["passed"]
        assert result["reason_code"] == "AMOUNT_OUT_OF_RANGE"


class TestMinMaxEventsCheck:
    def test_too_few_events_fails(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        events = [_make_event(t0)]
        c = _make_campaign_with_events(events)
        cfg = GatekeeperConfig(min_events=3)
        result = _check_min_max_events(c, cfg)
        assert not result["passed"]
        assert result["reason_code"] == "EVENT_COUNT_LOW"


class TestIntegration:
    """Full check suite integration tests."""

    def test_valid_campaign_passes_all_checks(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="test_then_bust")
        c = gen.generate_campaign(params)
        gk_cfg = GatekeeperConfig(
            min_amount=0.01,
            max_amount=50000.0,
            max_inter_event_gap_seconds=86400.0,
        )
        result = run_all_checks(c, gk_cfg)
        assert result.valid, f"Valid campaign rejected: {result.reason}"

    def test_valid_campaign_check_campaign_convenience(self):
        cfg = ForgeConfig(rng_seed=42)
        gen = CampaignGenerator(cfg)
        params = ForgeParams(seed=42, archetype_id="card_craftering", variant_name="test_then_bust")
        c = gen.generate_campaign(params)
        from argus.scout.taxonomy import TAXONOMY
        result = check_campaign(c, archetype_id="card_craftering", taxonomy=TAXONOMY)
        assert result.valid

    def test_empty_campaign_rejected(self):
        c = _make_campaign_with_events([])
        cfg = GatekeeperConfig(min_events=1)
        result = run_all_checks(c, cfg)
        assert not result.valid
        assert result.reason_code == "EVENT_COUNT_LOW"

    def test_invalid_campaign_returns_reason_code(self):
        t0 = datetime(2026, 1, 1, 12, 0, 0)
        t1 = t0 - timedelta(seconds=100)
        events = [_make_event(t0), _make_event(t1)]
        c = _make_campaign_with_events(events)
        result = run_all_checks(c)
        assert not result.valid
        assert result.reason_code is not None
        assert result.invalid_components
