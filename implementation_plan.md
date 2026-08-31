# Argus Implementation Plan

This document tracks the implementation of the Argus Cycle through its phases.

## Phase Overview

- [x] **Phase 0** — Repo scaffolding & environment
- [x] **Phase 1** — Scout (attack taxonomy)
- [x] **Phase 2** — Forge (synthetic payment simulator)
- [x] **Phase 3** — Gatekeeper (fidelity/validity firewall)
- [x] **Phase 4** — Wraith (adaptive red-team policy)
- [x] **Phase 5** — Sentinel (defender ensemble + hardening generations)
- [x] **Phase 6** — The Ledger (evidence & reproducibility pipeline)
- [x] **Phase 7** — Oracle (LLM narrative layer)
- [x] **Phase 8** — Argus Console (web dashboard)
- [x] **Phase 9** — Testing, docs, and packaging

## Detailed Plan

### Phase 0: Scaffolding
- Initialize directory layout (`argus/`, `tests/`, `data/`, `scripts/`, `dashboard/`)
- Python `pyproject.toml` with dependencies (numpy, pandas, scikit-learn, scipy, pydantic)
- `.env.example` for LLM provider keys
- README and `.gitignore`

### Phase 1: Scout
- Pydantic schema for `Archetype`, `EventSequence`, `EventSpec`
- 8 hand-authored archetypes with 2-4 variants each (~18 total variants)
- Validation: schema conformance, unique IDs, no impossible event order
- Versioned JSON at `argus/scout/data/taxonomy.json`

### Phase 2: Forge
- Deterministic, seeded synthetic simulator
- Entity graph (customers, devices, merchants, beneficiaries)
- Campaigns of 5-20 ordered events from a Scout archetype
- Track timing/velocity signals
- Generate legitimate (non-attack) pool for training/calibration

### Phase 3: Gatekeeper
- Schema conformance check
- Value-range sanity (amounts, timestamps)
- Event chronology (no time travel, sane gaps)
- Behavioral plausibility (velocity, entity reuse consistency)
- Archetype consistency check
- Invalid campaigns logged and discarded

### Phase 4: Wraith
- LinUCB contextual bandit over typed campaign parameters
- Context = recent Sentinel feedback only
- Reward = fidelity-weighted approved value - detection cost - resource cost
- Two baselines: random search, rule mutation
- Only Gatekeeper-valid campaigns earn reward

### Phase 5: Sentinel
- Ensemble: gradient-boosted classifier + isolation forest + graph risk
- Calibrate on disjoint legitimate split
- Generations: Sentinel-0 → Sentinel-1 → Sentinel-2
- Evaluate on held-out attack families (no leakage)
- Report ROC-AUC and recall

### Phase 6: The Ledger
- Multi-seed runner (5 seeds default)
- Per-seed + aggregated results saved as JSON
- Wilcoxon signed-rank significance tests
- Reality-check: reweight precision to realistic low base rate
- Fail-closed artifact loader

### Phase 7: Oracle
- LLM client supporting Anthropic, OpenAI, Google
- Three uses: design-time drafting, results narration, evidence chat
- Graceful degradation to templates when no API key
- Caching for repeated requests
- No key = Argus still works fully

### Phase 8: Argus Console
- Original visual identity (not generic template)
- Sections: mission brief, Scout explorer, Forge timeline, Wraith curve,
  Sentinel progression, Ledger, reality check, Oracle chat
- All numbers from Ledger artifacts (fail-closed)
- Loading/error/empty states for all data-driven views

### Phase 9: Hardening
- Run full test suite (pytest)
- Write architecture docs, CHANGELOG
- Convenience scripts (`run-demo`, `serve`)
- Final pass: no hardcoded keys, no real PII, all numbers traceable