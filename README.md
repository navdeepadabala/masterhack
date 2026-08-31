# Argus — Synthetic Defensive Payment-Fraud Research System

**An offline research/demo project — NOT connected to real payment rails or real cardholder data.**  
Everything runs on synthetic, generated data.

> The Argus Cycle turns fraud-detector evaluation into a governed learning loop:
> 
> 1. **Scout** — typed taxonomy of fraud attack archetypes and variants
> 2. **Forge** — deterministic synthetic payment-network simulator
> 3. **Gatekeeper** — validity/fidelity firewall
> 4. **Wraith** — adaptive red-team policy (LinUCB contextual bandit)
> 5. **Sentinel** — fraud-defender ensemble (supervised + unsupervised + graph risk)
> 6. **The Ledger** — versioned evidence artifacts and reproducibility pipeline
> 7. **Oracle** — LLM-assisted narrative layer (description drafting, results narration, evidence chat)
> 8. **Argus Console** — web dashboard for exploring results

## Quick Start

```bash
# 1. Clone & install
git clone <repo-url> argus
cd argus
pip install -e .

# 2. Copy example env (optional for Oracle LLM features)
cp .env.example .env
# Edit .env to set your LLM provider key (or leave unset for template fallback)

# 3. Run the full Argus Cycle pipeline and generate Ledger evidence
python -m argus.console run-demo

# 4. Start the web dashboard (serves on http://localhost:8000)
python -m argus.console serve

# 5. Run tests
pytest
```

## Responsible Use

See [`RESPONSIBLE_USE.md`](RESPONSIBLE_USE.md) for important guidelines.

## Project Status

This project implements the full **Argus Cycle** (phases 0–9). It is ready for reproducible research and experimentation with synthetic fraud detection.