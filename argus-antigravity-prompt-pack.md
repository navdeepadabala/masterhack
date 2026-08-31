# Argus — Antigravity Prompt Pack
### A rebranded, functionally-equivalent rebuild of the AegisLoop closed-loop fraud-simulation system

---

## How to use this document

Antigravity works best when it plans in phases (`task.md` → `implementation_plan.md` →
`walkthrough.md`) rather than being handed one giant undifferentiated task. So:

1. Open a new Antigravity project/conversation and paste **Master Brief** first, as-is.
   Let it acknowledge and generate its initial `implementation_plan.md`.
2. Paste **Phase 0**. Let it finish, verify (tests/build pass), and summarize in
   `walkthrough.md` before you move on.
3. Paste **Phase 1**, then **Phase 2**, etc., one at a time, in order. Each phase prompt
   assumes the previous ones are done — don't skip ahead even if it offers to.
4. If a phase is too big and Antigravity's context gets messy mid-phase, just say
   "pause here, summarize progress in walkthrough.md, we'll continue this phase next
   session" — then re-paste the same phase prompt in a fresh conversation; it will
   pick up from the artifacts on disk.

Everything below is written from scratch around the *functionality* AegisLoop
demonstrates (adversarial red-team/defender-hardening loop for payment fraud), with
new names throughout and room for you to make different UI/stack choices. No code or
text is copied from that repo.

---

## Rename map (used consistently below — change further if you like)

| Original concept | New name here |
|---|---|
| AegisLoop (product) | **Argus** |
| The closed loop | **The Argus Cycle** |
| Identify (threat atlas) | **Scout** |
| Generate (payment simulator) | **Forge** |
| Fidelity firewall | **Gatekeeper** |
| Adapt (LinUCB red-team bandit) | **Wraith** |
| Defend (ensemble + hardening generations) | **Sentinel** (generations: Sentinel-0 → Sentinel-1 → Sentinel-2) |
| Evidence/reproducibility artifacts | **The Ledger** |
| GenAI narrative/assist layer (uses your API key) | **Oracle** |
| Web dashboard | **Argus Console** |

---

## MASTER BRIEF (paste this first)

```
You are helping me build "Argus" — a synthetic, defensive payment-fraud research
system, from scratch. It's an offline research/demo project, NOT a production
fraud system and NOT connected to any real payment rails or real cardholder data.
Everything runs on synthetic, generated data.

CONCEPT
Argus turns fraud-detector evaluation into a governed learning loop instead of a
one-time model build, called "the Argus Cycle":

1. Scout — a hand-authored, typed taxonomy of fraud attack archetypes and variants
   (channel, rail, objective, event sequence, known mitigations). This is a safe,
   structured scenario schema — never a free-form "generate an attack" endpoint.
2. Forge — a deterministic, seeded, stateful synthetic payment-network simulator.
   It rolls out multi-event "campaigns" (roughly 5-20 ordered events) across
   persistent entities (customers, devices, merchants, beneficiaries) with realistic
   timing, velocity, and relationship reuse.
3. Gatekeeper — a validity/fidelity firewall that rejects malformed, out-of-range,
   chronologically impossible, or behaviorally implausible campaigns BEFORE they can
   earn any reward. Nothing invalid reaches the learning loop.
4. Wraith — an adaptive red-team policy (LinUCB contextual bandit) that selects
   full campaign strategies based only on recent black-box defender feedback
   (detected / not detected, confidence, cost). Compare it against a random-search
   baseline and a rule-mutation baseline.
5. Sentinel — a fraud-defender ensemble (supervised gradient-boosted classifier +
   unsupervised isolation-forest-style anomaly score + an explicit relationship/graph
   risk score). Calibrate it on a disjoint legitimate validation split, freeze it,
   let Wraith attack it, retrain on the successful evasions, and repeat — producing
   generations Sentinel-0 → Sentinel-1 → Sentinel-2. Each generation is evaluated on
   attack families held out from every prior stage (training, calibration, red-team
   search, hardening).
6. The Ledger — every headline number shown anywhere in the product must be loaded
   from a versioned evidence artifact on disk (JSON/CSV), never computed live in the
   UI and never hand-typed. Run experiments across multiple fixed random seeds (5 is
   a reasonable default) and report mean ± spread honestly, including any null or
   negative results — don't hide a finding because it's inconvenient.
7. Oracle — a GenAI narrative-assist layer that calls an LLM through an API key
   (configurable — Anthropic, OpenAI, or Gemini, your choice, read from an
   environment variable). Its ONLY jobs are: (a) helping draft/expand plain-language
   descriptions and mitigation text for Scout's attack taxonomy at design time, (b)
   turning Wraith/Sentinel numeric results into plain-language summaries for the
   dashboard, (c) an "ask the evidence" chat assistant that answers questions
   strictly grounded in Ledger artifacts. Oracle must NEVER invent metrics, must
   degrade gracefully to static templates if no API key is set, and must never be
   used to generate real attack instructions — only to describe the abstract,
   already-defined Scout archetypes in natural language.

REQUIREMENTS
- All data is synthetic. No real PII, no real payment-rail connectors, no scraped
  real transaction data anywhere.
- Reproducibility: fixed seeds, deterministic simulator, versioned artifacts, a
  fail-closed UI (if an expected evidence file is missing or malformed, show an
  error state — never fabricate a chart).
- Pick your own UI stack and visual design — it should look and feel clearly
  different from a typical dashboard template, not just re-skinned. You choose the
  frontend framework; propose one if I haven't specified it and tell me why.
- Python for the simulation/ML research runtime (NumPy/pandas/scikit-learn/SciPy is
  a reasonable default, but propose alternatives if you have a good reason).
- LLM API key must be read from an environment variable, never hardcoded, with a
  `.env.example` documenting it, and the app must run (in a degraded/template mode)
  with no key set at all.
- Include a short RESPONSIBLE_USE.md: synthetic-only, no real financial data, no
  operational attack instructions, defensive research purpose only.

Before writing any code, generate an implementation_plan.md that breaks the build
into the phases I'll paste one at a time. Confirm you understand the concept above,
ask me anything genuinely unclear, then wait for Phase 0.
```

---

## PHASE 0 — Repo scaffolding & environment

```
Phase 0 of Argus: scaffolding only, no feature logic yet.

- Initialize the repo with the directory layout for Argus (rename anything you like,
  but keep Scout / Forge / Gatekeeper / Wraith / Sentinel / Ledger / Oracle /
  Argus Console as the top-level module names so I can track them against the plan).
- Set up the Python environment (pyproject.toml or requirements.txt) and the
  frontend project for whatever stack you proposed.
- Add `.env.example` with a placeholder LLM_API_KEY (and note which provider it's
  for), plus any other config Argus will need.
- Add a basic CI-friendly test runner stub (pytest for Python; whatever the
  frontend stack's standard is) even though there's nothing to test yet — just
  confirm `pytest -q` and the frontend test command both run cleanly on empty stubs.
- Write a one-paragraph README stub describing Argus (use the concept from the
  Master Brief, in your own words).
- Update implementation_plan.md marking Phase 0 done, and write a short
  walkthrough.md entry.
```

---

## PHASE 1 — Scout (attack taxonomy)

```
Phase 1 of Argus: build Scout, the typed attack taxonomy.

- Design a schema (Pydantic on the Python side, mirrored with Zod if the frontend
  reads it directly) for an attack archetype: id, name, channel, rail, objective,
  a short event-sequence template, known mitigations, and a GenAI-enabler flag.
- Hand-author at least 6-8 archetypes with 3-4 variants each, stored as a versioned
  JSON file Scout loads at runtime — don't hardcode them in UI code.
- Write validation tests: every archetype must satisfy the schema, no duplicate ids,
  no archetype implies an impossible event order.
- Do NOT call Oracle/the LLM yet for this phase — write the archetype text yourself
  for now; Oracle-assisted drafting comes in the Oracle phase.
- Treat this taxonomy as fixed, safe, structured data — it's the only vocabulary
  later phases are allowed to draw from.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 2 — Forge (synthetic payment simulator)

```
Phase 2 of Argus: build Forge, the deterministic synthetic payment-network
simulator.

- Given a random seed and a chosen Scout archetype+variant, deterministically roll
  out an ordered campaign of 5-20 events across a small persistent entity graph:
  customers, devices, merchants, beneficiaries.
- Entities and relationships should persist and evolve across events within a
  campaign (e.g. a device gets reused, a beneficiary relationship gets established
  then exploited) — this is what makes it "entity-linked" rather than a flat list
  of independent transactions.
- Track realistic-feeling timing/velocity signals (inter-event gaps, amount
  patterns) as campaign features, since Sentinel will later need these as model
  inputs.
- Write determinism tests: same seed + same archetype => byte-identical campaign
  output, every time.
- Also generate a pool of ordinary/legitimate (non-attack) campaigns the same way,
  for later training/calibration splits.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 3 — Gatekeeper (fidelity/validity firewall)

```
Phase 3 of Argus: build Gatekeeper, sitting between Forge and everything downstream.

- Implement checks: schema conformance, value-range sanity, event chronology,
  behavioral plausibility (e.g. no impossible velocity), and entity-reuse
  consistency with the campaign's declared archetype.
- Gatekeeper must run on every campaign Forge produces, BEFORE it is eligible for
  any reward calculation in later phases. Invalid campaigns are logged and
  discarded, never silently passed through.
- Write tests using deliberately corrupted/invalid campaigns (bad timestamps,
  impossible amounts, orphaned entities) to confirm each is rejected with a clear
  reason code.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 4 — Wraith (adaptive red-team policy)

```
Phase 4 of Argus: build Wraith, the adaptive campaign-selection policy.

- Implement a LinUCB contextual bandit operating over typed campaign parameters
  (archetype, variant, and any tunable campaign-level knobs you exposed in Forge).
  Context per round = features summarizing recent Sentinel (defender) feedback only
  — no privileged access to Sentinel's internals.
- Define and log a reward function: fidelity-weighted approved value, minus
  detection cost, minus resource cost, with an optional first-novel-success bonus
  term you can toggle on/off. Log every component separately, not just the total.
- Implement two baselines for comparison: pure random campaign search, and a
  simple rule-mutation search. All three (Wraith, random, rule-mutation) must run
  under the same fixed campaign budget per experiment.
- Only Gatekeeper-valid campaigns are eligible for reward; invalid ones score zero
  and don't update the bandit.
- Write tests confirming Wraith's arm-selection updates correctly from feedback and
  that an invalid campaign never contributes reward.
- Do not hand-pick or hardcode "expected" performance numbers anywhere — whatever
  Wraith actually achieves against the baselines in your runs is the real result.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 5 — Sentinel (defender ensemble + hardening generations)

```
Phase 5 of Argus: build Sentinel, the defender, and the generational hardening loop.

- Build an ensemble: a supervised gradient-boosted classifier, an unsupervised
  anomaly score (isolation-forest style), and an explicit relationship/graph risk
  score derived from Forge's entity-reuse signals. Combine them into one score.
- Split data properly and keep the splits disjoint: training, a legitimate
  calibration/validation split, red-team search data, hardening data, and a FINAL
  held-out set of entire attack families that never appears anywhere upstream.
  Write a test that actively checks for split leakage (no shared campaign ids
  across splits).
- Implement the hardening loop: calibrate Sentinel-0, freeze it, run Wraith against
  it, take only the valid evasions with positive approved value as new hardening
  data, retrain and recalibrate into Sentinel-1, repeat once more into Sentinel-2.
- Evaluate every generation (0, 1, 2) on the SAME final held-out attack families,
  reporting ROC-AUC and recall at minimum.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 6 — The Ledger (evidence & reproducibility pipeline)

```
Phase 6 of Argus: build the Ledger, tying everything together into reproducible,
versioned evidence.

- Write a multi-seed experiment runner: repeat the full Scout->Forge->Gatekeeper->
  Wraith->Sentinel pipeline across 5 fixed seeds, saving per-seed and aggregated
  results (means, standard deviations, bootstrap confidence intervals) to versioned
  JSON/CSV artifacts.
- Add paired statistical significance tests (e.g. Wilcoxon signed-rank) comparing
  Wraith vs. each baseline across seeds, and report the result honestly even if
  it's not significant.
- Add a "reality check" calculator: given Sentinel-2's precision at whatever fraud
  prevalence your synthetic experiment actually has, reweight it to a realistic
  low base rate (e.g. ~0.01-0.02%) and report how precision changes. Label clearly
  that the connecting trend between the two points is illustrative interpolation,
  not additional measured data.
- Write a fail-closed artifact loader: any consumer (UI, CLI, tests) that requests
  a Ledger artifact and finds it missing or schema-invalid must error clearly, never
  fall back to fabricated placeholder numbers.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 7 — Oracle (LLM narrative layer — this is where the API key is used)

```
Phase 7 of Argus: build Oracle, the LLM-assisted narrative layer.

- Add an LLM client reading the API key from the environment variable set up in
  Phase 0 (support at least one provider fully; structure the client so swapping
  providers later is a small change, not a rewrite).
- Implement three narrow, grounded use cases only:
  1. Design-time drafting: given a Scout archetype's structured fields, ask the LLM
     to draft a clearer plain-language description and mitigation summary for a
     human to review and approve before it's saved — never auto-publish
     LLM-drafted taxonomy text without a review step.
  2. Results narration: given a Ledger artifact (numbers only), ask the LLM to
     write a short plain-language summary for the dashboard. Pass it the actual
     numbers as structured input — never let it guess or extrapolate figures it
     wasn't given.
  3. "Ask the evidence" chat: answer user questions about Argus's results by
     retrieving relevant Ledger artifacts and grounding the LLM's answer in them,
     declining to answer anything the artifacts don't cover rather than
     improvising.
- Implement graceful degradation: if no API key is set, Oracle falls back to
  simple static templates for (1) and (2), and (3) is disabled with a clear message
  — the rest of Argus must work fully without any LLM key.
- Add basic response caching so repeated identical requests don't re-hit the API.
- Write tests for the no-key fallback path and for the grounding behavior (mock the
  LLM call; assert the prompt sent to it actually contains the real numbers, not
  placeholders).
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 8 — Argus Console (web dashboard)

```
Phase 8 of Argus: build Argus Console, the dashboard.

- Design an original visual identity for Argus — pick a distinct name/theme,
  don't reuse a generic template look. Propose 2-3 direction options (e.g. color
  palette, typography, layout metaphor) and pick one, or ask me to pick.
- Build sections covering: a mission-brief landing view, a Scout taxonomy
  explorer, a Forge campaign-timeline viewer (visualize one rolled-out campaign
  step by step), a Wraith learning-curve view (bandit vs. baselines over rounds),
  a Sentinel generation-progression view (0->1->2 metrics), a Ledger/evidence
  view with links to the underlying artifact files, a reality-check panel (the
  prevalence/precision chart from Phase 6), and an Oracle chat panel.
- Every number displayed must come from a Ledger artifact fetched through the
  fail-closed loader from Phase 6 — no hardcoded demo numbers in UI components.
- Add loading/error/empty states for every data-driven view.
- Update implementation_plan.md and walkthrough.md.
```

---

## PHASE 9 — Testing, docs, and packaging

```
Phase 9 of Argus: final hardening pass.

- Run and fix the full test suite: Python (pytest) covering Scout schema safety,
  Forge determinism, Gatekeeper rejection cases, Wraith reward correctness and
  leakage checks, Sentinel split-disjointness; frontend unit + any end-to-end/
  accessibility tests for Argus Console.
- Write final docs: README (overview, how to run locally, how to reproduce the
  Ledger evidence from scratch), an architecture doc describing the Argus Cycle,
  a RESPONSIBLE_USE.md (synthetic-only, no real payment data, defensive research
  purpose, no operational attack instructions), and a short CHANGELOG.
- Add convenience run scripts (equivalent of a `run_demo` script) for both the
  Python reproduction pipeline and the web dashboard.
- Do a final pass confirming: no hardcoded API keys anywhere, no real PII/sample
  data snuck in anywhere, every dashboard number traces to a Ledger artifact.
- Update implementation_plan.md marking the project complete and write a final
  walkthrough.md summarizing what was built.
```
