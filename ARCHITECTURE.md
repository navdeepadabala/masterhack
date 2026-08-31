# Argus — Architecture

> A short reference for contributors. For the high-level concept, see
> [README.md](README.md). For usage constraints, see
> [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md).

## The Argus Cycle

```
                ┌──────────┐
                │  Scout   │   hand-authored, typed attack taxonomy
                └────┬─────┘
                     │  (archetype, variant)
                     ▼
                ┌──────────┐
                │  Forge   │   deterministic, seeded synthetic simulator
                └────┬─────┘
                     │  Campaign
                     ▼
                ┌──────────┐
                │ Gatekeeper│   validity/fidelity firewall
                └────┬─────┘
                     │  valid Campaign
              ┌──────┴──────┐
              ▼             ▼
        ┌──────────┐   ┌──────────┐
        │  Wraith  │   │ Sentinel │
        │ red-team │   │ defender │  ← feedback loop
        │  LinUCB  │   │ ensemble │
        └────┬─────┘   └────┬─────┘
             │ evasions     │ scores
             └──────┬───────┘
                    ▼
              ┌──────────┐
              │  Ledger  │   versioned evidence artifacts
              └────┬─────┘
                   │
                   ▼
              ┌──────────┐
              │  Oracle  │   LLM narrative layer
              └────┬─────┘
                   │
                   ▼
            ┌──────────────┐
            │ Argus Console│   web dashboard
            └──────────────┘
```

## Modules

| Module | Path | Role |
|---|---|---|
| `argus.scout` | `argus/scout/` | Typed attack taxonomy (schema + JSON) |
| `argus.forge` | `argus/forge/` | Deterministic synthetic simulator |
| `argus.gatekeeper` | `argus/gatekeeper/` | Validity/fidelity firewall |
| `argus.wraith` | `argus/wraith/` | LinUCB red-team bandit + baselines |
| `argus.sentinel` | `argus/sentinel/` | Defender ensemble + hardening loop |
| `argus.ledger` | `argus/ledger/` | Multi-seed runner + fail-closed loader |
| `argus.oracle` | `argus/oracle/` | LLM narrative layer (3 uses, no-key fallback) |
| `argus.console` | `argus/console/` | Web dashboard (stdlib http.server) |

## Data flow

1. **Scout** loads a versioned `taxonomy.json` (Pydantic-validated). This is
   the only vocabulary the rest of the cycle is allowed to use.

2. **Forge** takes `(seed, archetype_id, variant_name)` and deterministically
   generates a `Campaign` (ordered events across an entity graph). Same inputs
   always produce byte-identical output.

3. **Gatekeeper** runs checks (schema, ranges, chronology, plausibility,
   archetype consistency). An invalid campaign is **discarded** with a reason
   code and never earns reward in Wraith.

4. **Wraith** maintains a LinUCB bandit that picks a campaign arm each round.
   The defender's black-box feedback (detected / not, value, cost) forms the
   context. Three policies (LinUCB, random, rule-mutation) run under the same
   budget for honest comparison.

5. **Sentinel** is a 3-component ensemble:
   - Supervised gradient-boosted classifier
   - Unsupervised isolation-forest anomaly score
   - Explicit graph/risk score from entity-reuse signals
   
   Calibrated on a disjoint legitimate split, then frozen while Wraith attacks.
   Evasions become hardening data for the next generation (Sentinel-0 → 1 → 2).
   Every generation is evaluated on a final held-out attack-family split
   disjoint from training, calibration, red-team search, and hardening.

6. **The Ledger** runs the full Scout→Forge→Gatekeeper→Wraith→Sentinel pipeline
   across N fixed seeds (default 5). Saves per-seed and aggregated JSON artifacts
   with Wilcoxon significance tests. Computes a "reality check" by reweighting
   synthetic precision to realistic low prevalence (0.01–0.02%). The loader is
   fail-closed: missing or malformed artifacts raise, never fabricate.

7. **Oracle** wraps an LLM client (Anthropic / OpenAI / Google) for three
   narrow uses:
   - **Design-time drafting** — turn a Scout archetype's structured fields
     into a clearer plain-language description, for human review. Never
     auto-publishes.
   - **Results narration** — turn Ledger numbers into a short plain-language
     summary, passing the actual numbers as structured input so the LLM can't
     guess.
   - **Evidence chat** — answer user questions grounded in retrieved Ledger
     artifacts, declining to answer anything the artifacts don't cover.
   
   Falls back to static templates when no API key is set; chat is disabled
   without a key.

8. **Argus Console** is a stdlib-based HTTP server. The dashboard SPA
   (`/`) calls `/api/ledger/...` to read artifacts and `/api/oracle/...`
   to talk to Oracle. Every number shown is loaded from a Ledger
   artifact — there is no hardcoded demo data in the UI.

## Disjoint data splits (Phase 5)

Sentinel must be evaluated on attack families it has never seen. Splits are
created per-archetype from the input campaigns:

| Split | % | Used for |
|---|---|---|
| `train` | 40% | Supervised component of Sentinel |
| `calib` | 20% | Threshold calibration (legitimate-only) |
| `red_team` | 20% | Wraith search budget |
| `harden` | 10% | Hardening data for next generation |
| `holdout` | 10% | Final held-out attack families (NEVER seen upstream) |

`check_split_disjointness()` runs after every split to assert no campaign
id appears in more than one split.

## Reward decomposition (Wraith)

```
total = fidelity_value − detection_cost − resource_cost + novelty_bonus
```

- `fidelity_value = approved_value × fidelity_weight` (only if `evaded=True`)
- `detection_cost = detection_cost` (only if `evaded=False`)
- `resource_cost = resource_cost` (always)
- `novelty_bonus = novelty_bonus × novelty` (toggleable, only on first-novel-success)

Each component is logged separately so consumers can decompose totals.

## Reality check (Phase 6)

Synthetic experiments typically have much higher fraud prevalence than
production (e.g. 50% vs 0.01%). Naïve precision numbers are misleading.

The reality-check helper reweights Sentinel's measured precision to a
list of realistic prevalences using a power-law heuristic, **and labels
the connecting trend as illustrative interpolation, not additional
measured data**. The single measured data point is the synthetic one.

## Oracle failure modes (Phase 7)

- No API key set → fall back to static template (still marks response as
  `degraded=True`).
- API call fails → same fallback, with `error` in metadata.
- Evidence chat + no key → chat is **disabled** (not degraded), with a
  clear message to the user.
- Caching is per-prompt+context hash, with TTL and LRU eviction.

## Reproducibility guarantees

- All randomness goes through seeded `random.Random` or `numpy.random.Generator`.
- Same seed + same archetype + same variant = byte-identical campaign.
- All numerical results come from versioned JSON artifacts in `argus/ledger/data/`.
- The dashboard's fail-closed loader will raise rather than fabricate if
  an artifact is missing or schema-invalid.

## File layout

```
argus/
  __init__.py
  scout/
    schema.py            # Pydantic models
    taxonomy.py          # Loader + re-exporter
    data/
      taxonomy.json      # The versioned taxonomy
  forge/
    config.py
    simulator.py         # CampaignGenerator
  gatekeeper/
    config.py
    checks.py
  wraith/
    config.py
    policy.py            # LinUCB, baselines, WraithPolicy
  sentinel/
    config.py
    split.py
    ensemble.py
    train.py
  ledger/
    loader.py            # Fail-closed artifact loader
    stats.py             # Wilcoxon, bootstrap CI, reality check
    runner.py            # Multi-seed experiment runner
    data/                # Generated artifacts (per run)
  oracle/
    client.py            # Multi-provider LLM client
    uses.py              # Three grounded use cases
  console/
    server.py            # stdlib http.server
    static/
      styles.css         # "Signal" visual identity
      app.js             # Dashboard SPA
tests/
  test_scout.py
  test_forge.py
  test_gatekeeper.py
  test_wraith.py
  test_sentinel.py
  test_ledger.py
scripts/
  run-demo.py            # Full Argus Cycle runner
  serve.py               # Dashboard launcher
data/                    # (top-level, sample data if any)
```
