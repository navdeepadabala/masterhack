# Responsible Use

**Argus is a defensive research project.** Read this before using the code or any artifacts it produces.

## Scope and purpose

Argus exists to help researchers, engineers, and educators evaluate fraud-detection
systems against synthetic, reproducible adversarial campaigns. The intended use is
to **defend** real systems by improving their detectors through controlled
experimentation, not to commit fraud or operationalize the attack patterns.

## What Argus is

- **Synthetic only.** No real cardholder data, no real PII, no real payment-rail
  connectors, no scraped transaction data anywhere in the pipeline.
- **Reproducible.** All randomness is seeded. All numerical results come from
  versioned Ledger artifacts on disk.
- **Closed-vocabulary.** Attacks are drawn from Scout's hand-authored, typed
  archetype taxonomy — the same vocabulary used in public fraud-mitigation
  literature.
- **Degraded-mode safe.** The Oracle narrative layer falls back to static
  templates when no LLM API key is configured; the system never silently fabricates.

## What Argus is NOT

- **Not a real fraud system.** It is not connected to real PSPs, gateways,
  issuer processors, or merchant accounts.
- **Not an operational attack toolkit.** No code in this repo will help someone
  commit fraud against a real financial institution.
- **Not an excuse for rule evasion.** It is a research artifact for evaluating
  defenders; it is not endorsed for bypassing real fraud controls.
- **Not a source of generative attack instructions.** Oracle/LLM features only
  *describe* pre-defined Scout archetypes in plain language — they do not
  invent new attack strategies.

## What you must NOT do with this code

- Use the code, archetype definitions, or any generated campaign to commit or
  attempt fraud against a real financial institution, payment processor, card
  network, merchant, or individual.
- Connect Argus to any real-world payment data or system, even in a test environment.
- Repackage Argus's output (campaigns, archetypes, code) as operational attack
  guidance. The output of Argus is research data about defensive performance, not
  instructions for committing fraud.

## Reporting concerns

If you believe Argus content has been used to attempt real-world fraud, contact
the maintainers. If you find a way to use Argus outside its intended scope, that
is your responsibility — not ours, and not what the project is designed for.