"""Argus Console — minimal, self-contained dashboard server.

No external web framework dependencies — uses Python's stdlib ``http.server``
plus a tiny HTML+JS frontend. This keeps the project lightweight and avoids
the Node toolchain for the demo.

Endpoints:
    GET  /                       — Dashboard SPA
    GET  /styles.css             — Dashboard styles
    GET  /app.js                 — Dashboard app
    GET  /api/ledger             — List available Ledger artifacts
    GET  /api/ledger/{name}      — Latest version of an artifact
    GET  /api/ledger/{name}/{v}  — Specific version
    GET  /api/ledger/experiment_results — Convenience for the dashboard
    GET  /api/scout/taxonomy     — Scout taxonomy JSON
    GET  /api/forge/generate     — Generate a sample campaign (?seed=)
    GET  /api/oracle/status      — Oracle status (provider, key present)
    POST /api/oracle/ask         — Ask Oracle (evidence-grounded chat)
    POST /api/oracle/narrate     — Narrate a Ledger artifact
    POST /api/oracle/draft       — Draft an archetype description
    POST /api/run-demo           — Run the full Argus Cycle
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from argus.forge.config import ForgeConfig, ForgeParams
from argus.forge.simulator import CampaignGenerator
from argus.ledger.loader import (
    LEDGER_ROOT,
    list_artifacts,
    list_versions,
    load_artifact,
    save_artifact,
)
from argus.ledger.runner import run_experiments
from argus.oracle.uses import (
    ask_evidence,
    draft_archetype_description,
    narrate_results,
    oracle_status,
)
from argus.scout.taxonomy import TAXONOMY


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


@dataclass
class AppContext:
    """Shared context for the dashboard."""

    ledger_root: Path = LEDGER_ROOT
    artifacts_cache: dict[str, Any] | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def create_app() -> tuple[type[BaseHTTPRequestHandler], AppContext]:
    """Return a (RequestHandler, Context) pair ready to serve."""

    ctx = AppContext()

    class ArgusRequestHandler(BaseHTTPRequestHandler):
        # Make context accessible
        ctx_ref = ctx

        # Suppress noisy default logging
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

        # -------------------------------------------------------------------
        # Routing
        # -------------------------------------------------------------------

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/" or path == "/index.html":
                self._serve_dashboard()
            elif path == "/styles.css":
                self._serve_static("styles.css", "text/css")
            elif path == "/app.js":
                self._serve_static("app.js", "application/javascript")
            elif path == "/api/ledger":
                self._handle_list_artifacts()
            elif path == "/api/ledger/experiment_results":
                self._handle_artifact_latest("experiment_results")
            elif path.startswith("/api/ledger/"):
                parts = path[len("/api/ledger/"):].split("/")
                if len(parts) == 1:
                    name = parts[0]
                    self._handle_artifact_latest(name)
                elif len(parts) == 2:
                    name, version = parts[0], parts[1]
                    self._handle_artifact_version(name, version)
                else:
                    self._json_error(400, "Bad request")
            elif path == "/api/scout/taxonomy":
                self._handle_scout_taxonomy()
            elif path == "/api/forge/generate":
                self._handle_forge_generate(parsed)
            elif path == "/api/oracle/status":
                self._handle_oracle_status()
            else:
                self._json_error(404, f"Not found: {path}")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            body = self._read_body()

            if path == "/api/oracle/ask":
                self._handle_oracle_ask(body)
            elif path == "/api/oracle/narrate":
                self._handle_oracle_narrate(body)
            elif path == "/api/oracle/draft":
                self._handle_oracle_draft(body)
            elif path == "/api/run-demo":
                self._handle_run_demo(body)
            else:
                self._json_error(404, f"Not found: {path}")

        # -------------------------------------------------------------------
        # Handlers
        # -------------------------------------------------------------------

        def _serve_dashboard(self) -> None:
            html = DASHBOARD_HTML
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def _serve_static(self, filename: str, content_type: str) -> None:
            try:
                content = (STATIC_DIR / filename).read_text(encoding="utf-8")
            except FileNotFoundError:
                self._json_error(404, f"Static file not found: {filename}")
                return
            data = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle_list_artifacts(self) -> None:
            payload = {
                "artifacts": [
                    {"name": n, "versions": list_versions(n)}
                    for n in list_artifacts(self.ctx_ref.ledger_root)
                ],
            }
            self._json_response(payload)

        def _handle_artifact_latest(self, name: str) -> None:
            try:
                art = load_artifact(name, ledger_root=self.ctx_ref.ledger_root)
            except FileNotFoundError as e:
                self._json_error(404, str(e))
                return
            self._json_response(art.to_dict())

        def _handle_artifact_version(self, name: str, version: str) -> None:
            try:
                art = load_artifact(name, version, ledger_root=self.ctx_ref.ledger_root)
            except (FileNotFoundError, ValueError) as e:
                self._json_error(404, str(e))
                return
            self._json_response(art.to_dict())

        def _handle_oracle_status(self) -> None:
            self._json_response(oracle_status())

        def _handle_scout_taxonomy(self) -> None:
            """Return the Scout taxonomy as JSON."""
            self._json_response(TAXONOMY.model_dump())

        def _handle_forge_generate(self, parsed) -> None:
            """Generate a single Forge campaign."""
            seed = int(parse_qs(parsed.query).get("seed", ["42"])[0])
            try:
                cfg = ForgeConfig(rng_seed=seed)
                gen = CampaignGenerator(cfg)
                # Pick a deterministic archetype+variant
                arch = TAXONOMY.archetypes[seed % len(TAXONOMY.archetypes)]
                variant = arch.event_sequences[seed % len(arch.event_sequences)]
                params = ForgeParams(seed=seed, archetype_id=arch.id, variant_name=variant.name)
                campaign = gen.generate_campaign(params)
                self._json_response(campaign.to_dict())
            except Exception as e:
                self._json_error(500, f"Generation failed: {e}")

        def _handle_oracle_ask(self, body: dict[str, Any]) -> None:
            question = body.get("question", "")
            if not question:
                self._json_error(400, "Missing 'question' field")
                return

            # Collect all available artifacts as evidence
            artifacts: list[dict[str, Any]] = []
            for name in list_artifacts(self.ctx_ref.ledger_root):
                try:
                    art = load_artifact(name, ledger_root=self.ctx_ref.ledger_root)
                    artifacts.append(art.to_dict())
                except Exception:
                    pass

            response = ask_evidence(question, artifacts)
            self._json_response(response.to_dict())

        def _handle_oracle_narrate(self, body: dict[str, Any]) -> None:
            name = body.get("artifact_name", "experiment_results")
            try:
                art = load_artifact(name, ledger_root=self.ctx_ref.ledger_root)
            except FileNotFoundError as e:
                self._json_error(404, str(e))
                return

            response = narrate_results(art.to_dict())
            self._json_response({"response": response.to_dict(), "artifact_name": name})

        def _handle_oracle_draft(self, body: dict[str, Any]) -> None:
            archetype = body.get("archetype")
            if not archetype:
                self._json_error(400, "Missing 'archetype' field")
                return
            response = draft_archetype_description(archetype)
            self._json_response(response.to_dict())

        def _handle_run_demo(self, body: dict[str, Any]) -> None:
            n_seeds = int(body.get("n_seeds", 3))
            n_rounds = int(body.get("n_rounds", 20))
            n_campaigns = int(body.get("n_campaigns_per_seed", 100))
            results = run_experiments(
                n_seeds=n_seeds,
                n_rounds=n_rounds,
                n_campaigns_per_seed=n_campaigns,
            )
            version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            save_artifact("experiment_results", results, version, ledger_root=self.ctx_ref.ledger_root)
            self._json_response({
                "saved_version": version,
                "n_seeds": n_seeds,
                "n_rounds": n_rounds,
                "n_policies": len(results.get("aggregated", {}).get("policies", {})),
            })

        # -------------------------------------------------------------------
        # Helpers
        # -------------------------------------------------------------------

        def _read_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length == 0:
                return {}
            try:
                raw = self.rfile.read(content_length)
                return json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}

        def _json_response(self, data: dict[str, Any], status: int = 200) -> None:
            payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _json_error(self, status: int, message: str) -> None:
            self._json_response({"error": message, "status": status}, status=status)

    return ArgusRequestHandler, ctx


# ---------------------------------------------------------------------------
# Top-level server entry points
# ---------------------------------------------------------------------------


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the dashboard on the given host/port."""
    handler, ctx = create_app()
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Argus Console running at http://{host}:{port}")
    print(f"Ledger root: {ctx.ledger_root}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


def run_demo(
    n_seeds: int = 3,
    n_rounds: int = 20,
    n_campaigns_per_seed: int = 100,
) -> dict[str, Any]:
    """Run the full Argus Cycle and save results."""
    results = run_experiments(
        n_seeds=n_seeds,
        n_rounds=n_rounds,
        n_campaigns_per_seed=n_campaigns_per_seed,
    )
    version = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    save_artifact("experiment_results", results, version)
    print(f"Saved experiment results as v{version} (seeds={n_seeds}, rounds={n_rounds})")
    return {"version": version, "results": results}


def load_ledger_into_context(ledger_root: Path | None = None) -> dict[str, Any]:
    """Load all Ledger artifacts into a single dict (for the dashboard bootstrap)."""
    root = ledger_root or LEDGER_ROOT
    out: dict[str, Any] = {}
    for name in list_artifacts(root):
        versions = list_versions(name, root)
        if versions:
            try:
                art = load_artifact(name, versions[-1], root)
                out[name] = art.to_dict()
            except Exception:
                pass
    return out


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------


STATIC_DIR = Path(__file__).parent / "static"

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Argus Console</title>
<link rel="stylesheet" href="/styles.css" />
</head>
<body>
<header class="topbar">
  <div class="brand">
    <span class="logo">▲</span>
    <span class="title">Argus</span>
    <span class="subtitle">Synthetic Defensive Payment-Fraud Research</span>
  </div>
  <div class="oracle-status" id="oracle-status">Oracle: …</div>
</header>

<nav class="sections">
  <button data-section="mission" class="active">Mission Brief</button>
  <button data-section="scout">Scout</button>
  <button data-section="forge">Forge</button>
  <button data-section="wraith">Wraith</button>
  <button data-section="sentinel">Sentinel</button>
  <button data-section="ledger">Ledger</button>
  <button data-section="reality">Reality Check</button>
  <button data-section="oracle">Oracle Chat</button>
</nav>

<main id="content">
  <section id="mission" class="view active">
    <h1>Mission Brief</h1>
    <p class="lead">
      Argus turns fraud-detector evaluation into a governed learning loop —
      the Argus Cycle. It runs on synthetic data only.
    </p>
    <div class="pipeline">
      <div class="stage"><h3>Scout</h3><p>Hand-authored attack taxonomy</p></div>
      <div class="arrow">→</div>
      <div class="stage"><h3>Forge</h3><p>Deterministic simulator</p></div>
      <div class="arrow">→</div>
      <div class="stage"><h3>Gatekeeper</h3><p>Validity firewall</p></div>
      <div class="arrow">→</div>
      <div class="stage"><h3>Wraith</h3><p>LinUCB red-team</p></div>
      <div class="arrow">→</div>
      <div class="stage"><h3>Sentinel</h3><p>Defender ensemble</p></div>
      <div class="arrow">→</div>
      <div class="stage"><h3>Ledger</h3><p>Versioned evidence</p></div>
    </div>
    <div class="actions">
      <button id="run-demo-btn">Run Argus Cycle (small)</button>
      <span id="run-demo-status"></span>
    </div>
    <div id="run-summary" class="summary-box"></div>
  </section>

  <section id="scout" class="view">
    <h1>Scout — Attack Taxonomy</h1>
    <p>Hand-authored, typed attack archetypes. The only vocabulary the cycle may use.</p>
    <div id="scout-list" class="card-grid"></div>
  </section>

  <section id="forge" class="view">
    <h1>Forge — Synthetic Campaign Simulator</h1>
    <p>Deterministic campaigns rolled out from archetypes.</p>
    <div class="controls">
      <label>Seed <input id="forge-seed" type="number" value="42" /></label>
      <button id="forge-gen">Generate sample campaign</button>
    </div>
    <div id="forge-output" class="forge-output"></div>
  </section>

  <section id="wraith" class="view">
    <h1>Wraith — Adaptive Red-Team</h1>
    <p>LinUCB contextual bandit vs random + rule-mutation baselines.</p>
    <div id="wraith-chart" class="chart-area"></div>
    <div id="wraith-table" class="stats-table"></div>
  </section>

  <section id="sentinel" class="view">
    <h1>Sentinel — Defender Generations</h1>
    <p>Sentinel-0 → Sentinel-1 → Sentinel-2 across hardening loop.</p>
    <div id="sentinel-chart" class="chart-area"></div>
    <div id="sentinel-table" class="stats-table"></div>
  </section>

  <section id="ledger" class="view">
    <h1>The Ledger — Evidence Artifacts</h1>
    <p>All numbers below come from versioned JSON artifacts on disk. The dashboard never fabricates.</p>
    <div id="ledger-list"></div>
    <div id="ledger-detail" class="json-detail"></div>
  </section>

  <section id="reality" class="view">
    <h1>Reality Check</h1>
    <p>Reweighting Sentinel's precision to realistic low base rates.</p>
    <p class="note">The connecting line between synthetic and realistic points is illustrative interpolation, not additional measured data.</p>
    <div id="reality-chart" class="chart-area"></div>
    <div id="reality-table" class="stats-table"></div>
  </section>

  <section id="oracle" class="view">
    <h1>Oracle — Ask the Evidence</h1>
    <p>Grounded chat backed by Ledger artifacts. Disable if no LLM key is set.</p>
    <div id="oracle-status-detail"></div>
    <div class="chat">
      <textarea id="chat-input" placeholder="Ask about Wraith, Sentinel, or any artifact..."></textarea>
      <button id="chat-send">Send</button>
    </div>
    <div id="chat-output" class="chat-output"></div>
  </section>
</main>

<footer class="footer">
  Argus v0.1.0 — Synthetic, defensive research only. See RESPONSIBLE_USE.md.
</footer>

<script src="/app.js"></script>
</body>
</html>
"""