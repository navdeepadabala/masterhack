/**
 * Argus Console — frontend SPA
 * All numbers come from Ledger artifacts (fail-closed).
 * No hardcoded demo numbers.
 */

(function () {
  "use strict";

  // ─── State ────────────────────────────────────────────────────────────────
  const state = {
    currentSection: "mission",
    oracleAvailable: false,
    artifacts: [],
    currentArtifact: null,
    currentArtifactName: null,
    currentArtifactVersion: null,
    runningDemo: false,
  };

  // ─── API helpers ─────────────────────────────────────────────────────────
  function api(path, opts = {}) {
    return fetch(path, {
      headers: { "Content-Type": "application/json", ...opts.headers },
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then((r) => {
      if (!r.ok) throw new Error(`API error ${r.status}: ${r.statusText}`);
      return r.json();
    });
  }

  // ─── Navigation ──────────────────────────────────────────────────────────
  function initNav() {
    document.querySelectorAll("[data-section]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const section = btn.dataset.section;
        switchSection(section);
      });
    });
  }

  function switchSection(name) {
    state.currentSection = name;
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.querySelectorAll("[data-section]").forEach((b) => b.classList.remove("active"));
    document.getElementById(name)?.classList.add("active");
    document.querySelector(`[data-section="${name}"]`)?.classList.add("active");
    // lazy-load section content
    if (name === "scout") loadScout();
    if (name === "wraith") loadWraith();
    if (name === "sentinel") loadSentinel();
    if (name === "ledger") loadLedger();
    if (name === "reality") loadReality();
    if (name === "oracle") loadOracle();
  }

  // ─── Oracle status ────────────────────────────────────────────────────────
  function checkOracleStatus() {
    return api("/api/oracle/status")
      .then((data) => {
        state.oracleAvailable = data.has_key;
        const el = document.getElementById("oracle-status");
        if (!el) return;
        if (data.has_key) {
          el.textContent = `Oracle: ${data.provider} (${data.model})`;
          el.className = "oracle-status available";
        } else {
          el.textContent = "Oracle: no key — template mode";
          el.className = "oracle-status unavailable";
        }
      })
      .catch(() => {
        const el = document.getElementById("oracle-status");
        if (el) {
          el.textContent = "Oracle: offline";
          el.className = "oracle-status unavailable";
        }
      });
  }

  // ─── Mission / run demo ────────────────────────────────────────────────────
  function initMission() {
    const btn = document.getElementById("run-demo-btn");
    if (!btn) return;
    btn.addEventListener("click", runDemo);
  }

  async function runDemo() {
    const btn = document.getElementById("run-demo-btn");
    const status = document.getElementById("run-demo-status");
    const summary = document.getElementById("run-summary");
    if (!btn || !status || !summary) return;
    if (state.runningDemo) return;

    state.runningDemo = true;
    btn.disabled = true;
    status.textContent = "Running Argus Cycle...";
    summary.innerHTML = '<div class="state-loading"><div class="spinner"></div>Generating evidence...</div>';

    try {
      const result = await api("/api/run-demo", {
        method: "POST",
        body: { n_seeds: 3, n_rounds: 20, n_campaigns_per_seed: 80 },
      });
      status.textContent = `✓ Done — saved v${result.saved_version}`;
      summary.innerHTML = `
        <div style="color:var(--accent);font-family:var(--font-mono);font-size:0.8rem;">
          <div>Seeds: ${result.n_seeds} | Rounds: ${result.n_rounds}</div>
          <div>Policies: ${result.n_policies} | Version: ${result.saved_version}</div>
        </div>
      `;
      // Refresh artifacts
      state.artifacts = await api("/api/ledger");
    } catch (e) {
      status.textContent = "✗ Failed";
      summary.innerHTML = `<div class="state-error">${e.message}</div>`;
    } finally {
      state.runningDemo = false;
      btn.disabled = false;
    }
  }

  // ─── Scout ─────────────────────────────────────────────────────────────────
  async function loadScout() {
    const el = document.getElementById("scout-list");
    if (!el || el.children.length > 0) return; // already loaded
    el.innerHTML = '<div class="state-loading"><div class="spinner"></div>Loading taxonomy...</div>';
    try {
      const res = await api("/api/scout/taxonomy");
      renderScoutTaxonomy(res, el);
    } catch {
      el.innerHTML = '<div class="state-error">Failed to load Scout taxonomy. Run the demo first to generate Ledger artifacts.</div>';
    }
  }

  function renderScoutTaxonomy(data, container) {
    container.innerHTML = "";
    const archetypes = data.archetypes || [];
    archetypes.forEach((arch) => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-header">
          <span class="card-title">${escHtml(arch.name)}</span>
          <span class="card-badge">${escHtml(arch.channel)} / ${escHtml(arch.rail)}</span>
        </div>
        <p>${escHtml(arch.objective || arch.description || "")}</p>
        <div class="card-tags">
          ${(arch.mitigations || []).slice(0, 3).map((m) => `<span class="tag">${escHtml(m)}</span>`).join("")}
        </div>
        <div style="margin-top:0.5rem;font-family:var(--font-mono);font-size:0.7rem;color:var(--text-muted);">
          ${arch.event_sequences?.length || 0} variants
        </div>
      `;
      container.appendChild(card);
    });
    if (!archetypes.length) {
      container.innerHTML = '<div class="state-empty">No archetypes found. Run the demo first.</div>';
    }
  }

  // ─── Forge ─────────────────────────────────────────────────────────────────
  function initForge() {
    const btn = document.getElementById("forge-gen");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const seed = parseInt(document.getElementById("forge-seed")?.value || "42", 10);
      generateForgeCampaign(seed);
    });
    // Also generate one on load
    generateForgeCampaign(42);
  }

  async function generateForgeCampaign(seed) {
    const el = document.getElementById("forge-output");
    if (!el) return;
    el.innerHTML = '<div class="state-loading"><div class="spinner"></div>Generating...</div>';
    try {
      const res = await api(`/api/forge/generate?seed=${seed}`);
      el.innerHTML = escHtml(JSON.stringify(res, null, 2));
    } catch {
      el.innerHTML = '<div class="state-error">Failed to generate campaign. Run the demo first.</div>';
    }
  }

  // ─── Wraith ────────────────────────────────────────────────────────────────
  async function loadWraith() {
    const chartEl = document.getElementById("wraith-chart");
    const tableEl = document.getElementById("wraith-table");
    if (!chartEl || !tableEl) return;

    try {
      const res = await api("/api/ledger/experiment_results");
      renderWraithView(res, chartEl, tableEl);
    } catch {
      chartEl.innerHTML = '<div class="state-error">No experiment results. Run the Argus Cycle first.</div>';
      tableEl.innerHTML = "";
    }
  }

  function renderWraithView(data, chartEl, tableEl) {
    const agg = data?.aggregated || {};
    const policies = agg.policies || {};

    // Draw a simple bar chart using canvas
    chartEl.innerHTML = '<canvas id="wraith-canvas" height="160"></canvas>';
    const canvas = document.getElementById("wraith-canvas");
    drawBarChart(canvas, policies);

    // Stats table
    const rows = Object.entries(policies).map(([name, p]) => {
      const mean = (p.mean_avg_reward || 0).toFixed(4);
      const ci = `[${(p.ci_low || 0).toFixed(4)}, ${(p.ci_high || 0).toFixed(4)}]`;
      return `<tr><td>${escHtml(name)}</td><td class="number">${mean}</td><td class="number">${ci}</td></tr>`;
    }).join("");
    tableEl.innerHTML = `
      <table class="stats-table">
        <thead><tr><th>Policy</th><th>Mean Avg Reward</th><th>95% CI</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // ─── Sentinel ───────────────────────────────────────────────────────────────
  async function loadSentinel() {
    const chartEl = document.getElementById("sentinel-chart");
    const tableEl = document.getElementById("sentinel-table");
    if (!chartEl || !tableEl) return;

    try {
      const res = await api("/api/ledger/experiment_results");
      renderSentinelView(res, chartEl, tableEl);
    } catch {
      chartEl.innerHTML = '<div class="state-error">No experiment results. Run the Argus Cycle first.</div>';
      tableEl.innerHTML = "";
    }
  }

  function renderSentinelView(data, chartEl, tableEl) {
    const agg = data?.aggregated || {};
    const trends = agg.sentinel_generation_trends || {};

    chartEl.innerHTML = '<canvas id="sentinel-canvas" height="160"></canvas>';
    const canvas = document.getElementById("sentinel-canvas");
    drawTrendChart(canvas, trends);

    const keys = ["roc_auc", "recall", "precision"];
    const rows = keys.map((k) => {
      const t = trends[k] || {};
      return `<tr><td>${k.toUpperCase()}</td><td class="number">${(t.mean || 0).toFixed(4)}</td><td class="number">[${(t.ci_low || 0).toFixed(4)}, ${(t.ci_high || 0).toFixed(4)}]</td></tr>`;
    }).join("");
    tableEl.innerHTML = `
      <table class="stats-table">
        <thead><tr><th>Metric</th><th>Mean</th><th>95% CI</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  // ─── Ledger ─────────────────────────────────────────────────────────────────
  async function loadLedger() {
    const listEl = document.getElementById("ledger-list");
    const detailEl = document.getElementById("ledger-detail");
    if (!listEl || !detailEl) return;

    listEl.innerHTML = '<div class="state-loading"><div class="spinner"></div>Loading artifacts...</div>';
    try {
      state.artifacts = await api("/api/ledger");
      renderLedgerList(state.artifacts, listEl, detailEl);
    } catch {
      listEl.innerHTML = '<div class="state-error">Failed to load Ledger. Run the Argus Cycle first.</div>';
    }
  }

  function renderLedgerList(artifacts, listEl, detailEl) {
    if (!artifacts.length) {
      listEl.innerHTML = '<div class="state-empty">No artifacts found. Run the Argus Cycle first.</div>';
      detailEl.innerHTML = "";
      return;
    }
    listEl.innerHTML = artifacts.map((a) => `
      <div class="ledger-item${a.name === state.currentArtifactName ? " selected" : ""}" data-name="${escHtml(a.name)}">
        <span class="ledger-item-name">${escHtml(a.name)}</span>
        <span class="ledger-item-versions">${a.versions?.length || 0} version(s)</span>
      </div>
    `).join("");

    listEl.querySelectorAll(".ledger-item").forEach((item) => {
      item.addEventListener("click", () => {
        const name = item.dataset.name;
        state.currentArtifactName = name;
        state.currentArtifact = artifacts.find((a) => a.name === name);
        loadArtifactVersion(name, null, detailEl);
        // Update selected
        listEl.querySelectorAll(".ledger-item").forEach((i) => i.classList.remove("selected"));
        item.classList.add("selected");
      });
    });

    // Auto-select first
    if (!state.currentArtifactName && artifacts.length > 0) {
      const first = listEl.querySelector(".ledger-item");
      first?.click();
    }
  }

  async function loadArtifactVersion(name, version, detailEl) {
    const url = version ? `/api/ledger/${name}/${version}` : `/api/ledger/${name}`;
    try {
      const art = await api(url);
      state.currentArtifact = art;
      state.currentArtifactVersion = art.version;
      detailEl.innerHTML = escHtml(JSON.stringify(art.data || art, null, 2));
    } catch {
      detailEl.innerHTML = '<div class="state-error">Failed to load artifact.</div>';
    }
  }

  // ─── Reality check ─────────────────────────────────────────────────────────
  async function loadReality() {
    const chartEl = document.getElementById("reality-chart");
    const tableEl = document.getElementById("reality-table");
    if (!chartEl || !tableEl) return;

    try {
      const res = await api("/api/ledger/experiment_results");
      renderRealityView(res, chartEl, tableEl);
    } catch {
      chartEl.innerHTML = '<div class="state-error">No experiment results. Run the Argus Cycle first.</div>';
      tableEl.innerHTML = "";
    }
  }

  function renderRealityView(data, chartEl, tableEl) {
    const reality = data?.aggregated?.reality_check || {};
    const synthetic = reality.synthetic_point || {};
    const points = reality.realistic_points || [];

    chartEl.innerHTML = '<canvas id="reality-canvas" height="200"></canvas>';
    const canvas = document.getElementById("reality-canvas");
    drawRealityChart(canvas, synthetic, points);

    const rows = points.map((pt) =>
      `<tr><td>${(pt.prevalence * 100).toFixed(4)}%</td><td class="number">${pt.precision.toFixed(4)}</td></tr>`
    ).join("");
    tableEl.innerHTML = `
      <table class="stats-table">
        <thead><tr><th>Prevalence</th><th>Precision (est.)</th></tr></thead>
        <tbody>
          <tr><td>Synthetic: ${((synthetic.prevalence || 0) * 100).toFixed(1)}%</td><td class="number">${(synthetic.precision || 0).toFixed(4)}</td></tr>
          ${rows}
        </tbody>
      </table>
      <p class="note">${escHtml(reality.note || "")}</p>
    `;
  }

  // ─── Oracle chat ────────────────────────────────────────────────────────────
  async function loadOracle() {
    const statusEl = document.getElementById("oracle-status-detail");
    const outputEl = document.getElementById("chat-output");
    if (!statusEl || !outputEl) return;

    // Status detail
    try {
      const status = await api("/api/oracle/status");
      statusEl.innerHTML = state.oracleAvailable
        ? `<span class="success">Oracle active — ${status.provider} / ${status.model}</span>`
        : `<span class="degraded">Oracle disabled — no API key. Using static templates.</span>`;
    } catch {
      statusEl.innerHTML = '<span class="error">Oracle unreachable</span>';
    }

    // Send button
    const sendBtn = document.getElementById("chat-send");
    const inputEl = document.getElementById("chat-input");
    if (sendBtn) {
      sendBtn.addEventListener("click", () => {
        const question = inputEl?.value?.trim();
        if (!question) return;
        sendOracleQuestion(question, outputEl, inputEl);
      });
    }
  }

  async function sendOracleQuestion(question, outputEl, inputEl) {
    if (!state.oracleAvailable) {
      outputEl.innerHTML = `<span class="degraded">Oracle chat requires an LLM API key. Set LLM_PROVIDER and the matching key env var.</span>`;
      return;
    }
    outputEl.innerHTML = '<div class="state-loading"><div class="spinner"></div>Oracle is thinking...</div>';
    try {
      const res = await api("/api/oracle/ask", {
        method: "POST",
        body: { question },
      });
      const degraded = res.degraded ? " (template fallback)" : "";
      outputEl.innerHTML = `<span class="success">${escHtml(res.text || "(no response)")}${degraded}</span>`;
      if (inputEl) inputEl.value = "";
    } catch (e) {
      outputEl.innerHTML = `<span class="error">Error: ${escHtml(e.message)}</span>`;
    }
  }

  // ─── Chart helpers ──────────────────────────────────────────────────────────
  function drawBarChart(canvas, policies) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width = canvas.parentElement.clientWidth || 600;
    const H = canvas.height;
    const keys = Object.keys(policies);
    if (!keys.length) return;

    ctx.clearRect(0, 0, W, H);
    const barW = Math.min(60, (W - 40) / keys.length - 10);
    const maxVal = Math.max(...keys.map((k) => Math.abs(policies[k]?.mean_avg_reward || 0)), 0.01);

    keys.forEach((k, i) => {
      const val = policies[k]?.mean_avg_reward || 0;
      const barH = Math.max(2, (Math.abs(val) / maxVal) * (H - 40));
      const x = 20 + i * (barW + 10);
      const y = H - 20 - barH;
      const color = k === "wraith_linucb" ? "#4dff91" : k === "random" ? "#4da6ff" : "#ffb84d";
      ctx.fillStyle = color;
      ctx.fillRect(x, y, barW, barH);
      ctx.fillStyle = "#8a9190";
      ctx.font = "10px JetBrains Mono, monospace";
      ctx.textAlign = "center";
      ctx.fillText(k.replace("wraith_", "w.").substring(0, 10), x + barW / 2, H - 6);
      ctx.fillText(val.toFixed(3), x + barW / 2, y - 4);
    });
  }

  function drawTrendChart(canvas, trends) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width = canvas.parentElement.clientWidth || 600;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const keys = ["roc_auc", "recall", "precision"];
    const colors = { roc_auc: "#4dff91", recall: "#4da6ff", precision: "#ffb84d" };
    const labels = ["Gen 0", "Gen 1", "Gen 2"];

    // Draw horizontal grid lines
    ctx.strokeStyle = "#2a2e2c";
    ctx.lineWidth = 1;
    for (let y = 0; y <= 1; y += 0.25) {
      const yPos = H - 20 - y * (H - 40);
      ctx.beginPath();
      ctx.moveTo(40, yPos);
      ctx.lineTo(W - 10, yPos);
      ctx.stroke();
    }

    // Y axis labels
    ctx.fillStyle = "#5a6160";
    ctx.font = "9px monospace";
    ctx.textAlign = "right";
    for (let y = 0; y <= 1; y += 0.25) {
      const yPos = H - 20 - y * (H - 40);
      ctx.fillText(y.toFixed(2), 36, yPos + 3);
    }

    // X axis labels
    ctx.textAlign = "center";
    labels.forEach((l, i) => {
      const x = 50 + i * ((W - 60) / 2);
      ctx.fillText(l, x + ((W - 60) / 4), H - 5);
    });

    // Plot each metric as a line
    const xStep = (W - 60) / 3;
    keys.forEach((key) => {
      const t = trends[key] || {};
      const mean = t.mean || 0.5;
      ctx.fillStyle = colors[key];
      const x = 50 + xStep * 0;
      const y = H - 20 - mean * (H - 40);
      ctx.beginPath();
      ctx.arc(x + xStep, y, 4, 0, Math.PI * 2);
      ctx.fill();
      // Show value
      ctx.font = "9px monospace";
      ctx.fillText(mean.toFixed(3), x + xStep, y - 8);
    });
  }

  function drawRealityChart(canvas, synthetic, points) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width = canvas.parentElement.clientWidth || 600;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const allPoints = [{ ...synthetic, isSynthetic: true }, ...points.map((p) => ({ ...p, isSynthetic: false }))];
    const maxPrev = Math.max(...allPoints.map((p) => p.prevalence || 0.5), 0.5);

    const padX = 50, padY = 20;
    const chartW = W - padX - 20;
    const chartH = H - padY - 30;

    // Grid
    ctx.strokeStyle = "#2a2e2c";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padY + (i / 4) * chartH;
      ctx.beginPath();
      ctx.moveTo(padX, y);
      ctx.lineTo(W - 20, y);
      ctx.stroke();
    }

    // Axes
    ctx.strokeStyle = "#5a6160";
    ctx.beginPath();
    ctx.moveTo(padX, padY);
    ctx.lineTo(padX, H - 30);
    ctx.lineTo(W - 20, H - 30);
    ctx.stroke();

    // Plot points
    allPoints.forEach((pt, idx) => {
      const x = padX + (pt.prevalence / maxPrev) * chartW;
      const y = padY + (1 - pt.precision) * chartH;
      const color = pt.isSynthetic ? "#4dff91" : "#4da6ff";
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, pt.isSynthetic ? 6 : 4, 0, Math.PI * 2);
      ctx.fill();
      // Label
      ctx.fillStyle = "#8a9190";
      ctx.font = "9px monospace";
      ctx.textAlign = "center";
      ctx.fillText(`${(pt.prevalence * 100).toFixed(2)}%`, x, H - 15);
    });

    // Connecting line (illustrative only — dashed)
    if (allPoints.length > 1) {
      ctx.strokeStyle = "#4dff91";
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      allPoints.forEach((pt, i) => {
        const x = padX + (pt.prevalence / maxPrev) * chartW;
        const y = padY + (1 - pt.precision) * chartH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }

  // ─── Utility ────────────────────────────────────────────────────────────────
  function escHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ─── Bootstrap ──────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    initNav();
    initMission();
    initForge();
    checkOracleStatus();
    // Initial section content
    if (state.currentSection === "mission") {
      loadScout();
    }
  });
})();
