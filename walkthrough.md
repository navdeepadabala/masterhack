# Argus Walkthrough

A running record of progress through the Argus Cycle phases.

## Phase 0: Scaffolding ✓
Created the directory structure (`argus/`, `tests/`, `data/`, `scripts/`, `dashboard/`),
Python `pyproject.toml` with numpy/pandas/scikit-learn/scipy/pydantic dependencies,
`.env.example` for Oracle LLM keys, `.gitignore`, README stub, and RESPONSIBLE_USE.md.

## Phase 1: Scout ✓
Built the typed attack taxonomy schema (Pydantic models for `Archetype`,
`EventSequence`, `EventSpec`) and a versioned JSON with 8 archetypes × 2-4
variants each (~18 variants). Archetypes cover: card craftering, account takeover,
friendly fraud, merchant collusion, synthetic ID fraud, device farm, beneficiary
fraud, first-party fraud.

## Phase 2: Forge ✓
Deterministic, seeded synthetic payment simulator. Rolls out ordered campaign
events from a Scout archetype+variant across a persistent entity graph
(customers, devices, merchants, beneficiaries). Same seed + same archetype →
byte-identical output.

## Phase 3: Gatekeeper ✓
Validity/fidelity firewall sitting between Forge and everything downstream.
Rejects schema-incompatible, out-of-range, chronologically impossible, or
behaviorally implausible campaigns with clear reason codes. Invalid campaigns
score zero reward in Wraith.

## Phase 4: Wraith ✓
LinUCB contextual bandit operating over typed campaign parameters. Context per
round = recent Sentinel feedback only. Reward = fidelity-weighted approved
value − detection cost − resource cost. Compared against random and rule-mutation
baselines under the same fixed campaign budget.

## Phase 5: Sentinel ✓
Defender ensemble: gradient-boosted classifier + isolation-forest-style anomaly
score + relationship/graph risk score. Generations Sentinel-0 → Sentinel-1 →
Sentinel-2 trained on evasions from the previous generation. Evaluated on a
held-out attack family set (disjoint from training, calibration, red-team search,
and hardening).

## Phase 6: The Ledger ✓
Multi-seed experiment runner (5 seeds default), per-seed + aggregated JSON
artifacts, Wilcoxon signed-rank significance tests, reality-check precision
reweighting to realistic low base rate, and a fail-closed artifact loader.

## Phase 7: Oracle ✓
LLM narrative layer with three narrow uses: design-time drafting, results
narration, evidence chat. Supports Anthropic, OpenAI, Google providers.
Graceful degradation to static templates when no API key is set. Caching for
repeated identical requests. No-key fallback tested.

## Phase 8: Argus Console ✓
Web dashboard with original visual identity (custom theme, not generic template).
Sections: mission brief, Scout taxonomy explorer, Forge campaign timeline,
Wraith learning curve, Sentinel generation progression, Ledger/evidence view,
reality check panel, Oracle chat. All numbers sourced from Ledger (fail-closed).

## Phase 9: Hardening ✓
Full pytest test suite covering Scout schema, Forge determinism, Gatekeeper
rejection, Wraith reward correctness, Sentinel split-disjointness, Ledger loaders.
Convenience scripts (`run-demo`, `serve`). Final docs (README, architecture,
RESPONSIBLE_USE, CHANGELOG).