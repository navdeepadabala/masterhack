# Changelog

All notable changes to Argus are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-31

### Added

- **Scout** — Hand-authored, typed attack taxonomy with 8 archetypes × 2–4 variants
  each (~18 variants). Pydantic schema validation, versioned JSON on disk.
  Archetypes: card craftering, account takeover, friendly fraud, merchant collusion,
  synthetic ID fraud, device farm, beneficiary fraud, first-party fraud.

- **Forge** — Deterministic, seeded synthetic payment-network simulator. Rolls out
  ordered campaign events across a persistent entity graph (customers, devices,
  merchants, beneficiaries). Same seed + same archetype → byte-identical output.
  Tracks timing/velocity/graph features for Sentinel.

- **Gatekeeper** — Validity/fidelity firewall sitting between Forge and everything
  downstream. Checks: schema conformance, value-range sanity, event chronology,
  behavioral plausibility, archetype consistency. Invalid campaigns score zero
  reward in Wraith.

- **Wraith** — LinUCB contextual bandit operating over typed campaign parameters.
  Context per round = recent Sentinel feedback only. Reward = fidelity-weighted
  approved value − detection cost − resource cost. Two baselines: random search
  and rule-mutation. All three run under the same fixed campaign budget.

- **Sentinel** — Defender ensemble: gradient-boosted classifier + isolation forest
  + relationship/graph risk score. Disjoint data splits (train, calib, red_team,
  harden, holdout). Generations Sentinel-0 → Sentinel-1 → Sentinel-2 via
  hardening loop on Wraith evasions. Evaluated on held-out attack families.

- **The Ledger** — Multi-seed experiment runner (5 seeds default), per-seed and
  aggregated JSON artifacts, Wilcoxon signed-rank significance tests, reality-check
  precision reweighting to realistic low base rates, fail-closed artifact loader.

- **Oracle** — LLM narrative layer supporting Anthropic, OpenAI, and Google Gemini.
  Three narrow uses: design-time archetype description drafting (human-reviewed),
  results narration, evidence-grounded chat. Graceful degradation to static
  templates when no API key is set. Caching for repeated requests.

- **Argus Console** — Web dashboard (stdlib http.server, no Node needed) with
  original "Signal" visual identity. Sections: mission brief, Scout taxonomy
  explorer, Forge campaign timeline, Wraith learning curve, Sentinel generation
  progression, Ledger/evidence view, reality check panel, Oracle chat.
  All numbers sourced from Ledger (fail-closed).

- **Tests** — pytest suite covering Scout schema safety, Forge determinism,
  Gatekeeper rejection cases, Wraith reward correctness, Sentinel split-disjointness,
  Ledger fail-closed loaders.

- **Docs** — README, architecture, RESPONSIBLE_USE.

- **Scripts** — `scripts/run-demo.py` and `scripts/serve.py` convenience entry points.
