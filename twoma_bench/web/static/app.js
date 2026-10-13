// 2M AI Bench (2MA-Bench) Dashboard Frontend Application

let currentRunId = null;
let currentSummary = null;
let radarChartInstance = null;
let eventSource = null;

const DIMENSION_LABELS = {
  smt_logic: "SMT Constraints",
  vm_emulation: "VM Register Emulation",
  counterfactual: "Counterfactual Logic",
  concurrency: "Concurrency Repair",
  epistemic: "Epistemic Impossibility",
};

document.addEventListener("DOMContentLoaded", () => {
  initRadarChart();
  setupEventListeners();
});

function initRadarChart() {
  const ctx = document.getElementById("radar-chart").getContext("2d");
  const labels = Object.values(DIMENSION_LABELS);

  radarChartInstance = new Chart(ctx, {
    type: "radar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Hardness Score (%)",
          data: [0, 0, 0, 0, 0],
          backgroundColor: "rgba(0, 243, 255, 0.2)",
          borderColor: "#00f3ff",
          borderWidth: 2,
          pointBackgroundColor: "#9d4edd",
          pointBorderColor: "#fff",
          pointHoverBackgroundColor: "#fff",
          pointHoverBorderColor: "#9d4edd",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          angleLines: { color: "rgba(255, 255, 255, 0.1)" },
          grid: { color: "rgba(255, 255, 255, 0.08)" },
          pointLabels: {
            color: "#8b9bb4",
            font: { size: 10, family: "'Inter', sans-serif" },
          },
          suggestedMin: 0,
          suggestedMax: 100,
          ticks: {
            display: false,
            stepSize: 20,
          },
        },
      },
      plugins: {
        legend: { display: false },
      },
    },
  });
}

function updateRadarChart(dimensionScores) {
  if (!radarChartInstance) return;
  const keys = Object.keys(DIMENSION_LABELS);
  const data = keys.map((k) => dimensionScores[k] || 0);
  radarChartInstance.data.datasets[0].data = data;
  radarChartInstance.update();
}

function setupEventListeners() {
  const providerSelect = document.getElementById("provider-select");
  const baseUrlInput = document.getElementById("base-url");
  const modelInput = document.getElementById("model-name");

  providerSelect.addEventListener("change", () => {
    const p = providerSelect.value;
    if (p === "anthropic") {
      baseUrlInput.value = "https://api.anthropic.com/v1";
      modelInput.value = "claude-3-7-sonnet";
    } else if (p === "gemini") {
      baseUrlInput.value = "https://generativelanguage.googleapis.com/v1beta/openai";
      modelInput.value = "gemini-2.5-pro";
    } else if (p === "deepseek") {
      baseUrlInput.value = "https://api.deepseek.com/v1";
      modelInput.value = "deepseek-reasoner";
    } else if (p === "ollama") {
      baseUrlInput.value = "http://localhost:11434/v1";
      modelInput.value = "llama3.3:70b";
    } else if (p === "mock") {
      baseUrlInput.value = "http://localhost:8088";
      modelInput.value = "mock-oracle-v1";
    } else {
      baseUrlInput.value = "https://api.openai.com/v1";
      modelInput.value = "gpt-4o";
    }
  });

  document.getElementById("btn-random-seed").addEventListener("click", () => {
    document.getElementById("eval-seed").value = Math.floor(Math.random() * 900000) + 100000;
  });

  document.getElementById("btn-test-connection").addEventListener("click", testConnection);
  document.getElementById("btn-start-benchmark").addEventListener("click", launchBenchmark);
  document.getElementById("btn-export-json").addEventListener("click", exportJson);
  document.getElementById("btn-export-csv")?.addEventListener("click", exportCsv);
  document.getElementById("btn-export-md").addEventListener("click", exportMarkdown);
  document.getElementById("btn-compare-runs")?.addEventListener("click", openCompareModal);

  document.getElementById("btn-close-modal").addEventListener("click", () => {
    document.getElementById("detail-modal").style.display = "none";
  });

  document.getElementById("btn-close-compare-modal")?.addEventListener("click", () => {
    document.getElementById("compare-modal").style.display = "none";
  });

  document.getElementById("btn-execute-compare")?.addEventListener("click", executeComparison);
}

function getApiBaseUrl() {
  if (window.location.protocol === "file:") {
    return "http://localhost:8088";
  }
  return window.location.origin;
}

async function testConnection() {
  const statusEl = document.getElementById("connection-status");
  statusEl.style.color = "var(--accent-cyan)";
  statusEl.textContent = "Testing connection...";

  const payload = {
    provider: document.getElementById("provider-select").value,
    base_url: document.getElementById("base-url").value,
    api_key: document.getElementById("api-key").value,
    model: document.getElementById("model-name").value,
  };

  try {
    const apiUrl = getApiBaseUrl() + "/api/test-connection";
    const res = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Backend (${apiUrl}) returned HTTP ${res.status}: ${text.slice(0, 150) || "Empty response"}`);
    }
    if (data.success) {
      statusEl.style.color = "var(--accent-green)";
      statusEl.textContent = "✓ " + data.message;
    } else {
      statusEl.style.color = "var(--accent-red)";
      statusEl.textContent = "✕ " + data.message;
    }
  } catch (err) {
    statusEl.style.color = "var(--accent-red)";
    let msg = err.message;
    if (window.location.protocol === "file:" && (msg.includes("Failed to fetch") || msg.includes("NetworkError"))) {
      msg += " (Make sure '2ma-bench serve --port 8088' is running in your terminal!)";
    }
    statusEl.textContent = "✕ Error: " + msg;
  }
}

async function launchBenchmark() {
  const selectedDims = Array.from(document.querySelectorAll("input[name='dimensions']:checked")).map(
    (el) => el.value
  );

  if (selectedDims.length === 0) {
    alert("Please select at least one benchmark dimension.");
    return;
  }

  const payload = {
    provider: document.getElementById("provider-select").value,
    base_url: document.getElementById("base-url").value,
    api_key: document.getElementById("api-key").value,
    model: document.getElementById("model-name").value,
    seed: parseInt(document.getElementById("eval-seed").value, 10),
    difficulty: parseInt(document.getElementById("eval-difficulty").value, 10),
    samples_per_dimension: parseInt(document.getElementById("eval-samples-per-dim")?.value || "1", 10),
    max_concurrency: parseInt(document.getElementById("eval-concurrency")?.value || "2", 10),
    max_tokens: parseInt(document.getElementById("eval-max-tokens")?.value || "8192", 10),
    dimensions: selectedDims,
  };

  const startBtn = document.getElementById("btn-start-benchmark");
  startBtn.disabled = true;
  startBtn.textContent = "Evaluating...";

  document.getElementById("run-status-badge").textContent = "RUNNING";
  document.getElementById("run-status-badge").className = "badge tag-running";
  document.getElementById("event-list").innerHTML = "";
  document.getElementById("progress-bar").style.width = "0%";

  try {
    const apiUrl = getApiBaseUrl() + "/api/run";
    const res = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      throw new Error(`Server returned HTTP ${res.status}: ${text.slice(0, 150)}`);
    }
    currentRunId = data.run_id;
    startEventStream(currentRunId);
  } catch (err) {
    alert("Failed to start run: " + err.message);
    startBtn.disabled = false;
    startBtn.textContent = "🚀 Launch 2MA-Bench Run";
  }
}

function startEventStream(runId) {
  if (eventSource) {
    eventSource.close();
  }

  const streamUrl = getApiBaseUrl() + `/api/stream/${runId}`;
  eventSource = new EventSource(streamUrl);

  eventSource.onmessage = (e) => {
    try {
      const event = JSON.parse(e.data);
      handleServerEvent(event);
    } catch (err) {
      console.error("Error parsing SSE:", err);
    }
  };

  eventSource.onerror = (err) => {
    console.warn("EventSource closed or disconnected:", err);
    eventSource.close();
  };
}

function handleServerEvent(event) {
  const eventList = document.getElementById("event-list");
  const progressBar = document.getElementById("progress-bar");

  if (event.type === "problem_started") {
    const item = document.createElement("div");
    item.className = "event-item";
    item.id = `item-${event.problem_id}`;
    item.innerHTML = `
      <div class="event-info">
        <div class="event-title">[${event.index}/${event.total}] ${event.title}</div>
        <div class="event-meta">${event.dimension_name}</div>
      </div>
      <span class="badge tag-running">TESTING</span>
    `;
    eventList.appendChild(item);
    item.scrollIntoView({ behavior: "smooth", block: "nearest" });

    const pct = ((event.index - 1) / event.total) * 100;
    progressBar.style.width = `${pct}%`;
  } else if (event.type === "problem_completed") {
    const item = document.getElementById(`item-${event.problem_id}`);
    if (item) {
      const tagClass = event.passed ? "tag-pass" : "tag-fail";
      const tagText = event.passed ? `PASSED (${Math.round(event.score * 100)}%)` : "FAILED";
      const metaExtra = `${event.tokens} tokens • ${Math.round(event.latency_ms)}ms`;

      item.innerHTML = `
        <div class="event-info">
          <div class="event-title">[${event.index}/${event.total}] ${DIMENSION_LABELS[event.dimension] || event.dimension}</div>
          <div class="event-meta">${metaExtra} ${event.failure_reason ? "• " + event.failure_reason : ""}</div>
        </div>
        <span class="badge ${tagClass}">${tagText}</span>
      `;
    }

    const pct = (event.index / event.total) * 100;
    progressBar.style.width = `${pct}%`;
  } else if (event.type === "run_completed") {
    currentSummary = event.summary;
    document.getElementById("run-status-badge").textContent = "COMPLETED";
    document.getElementById("run-status-badge").className = "badge tag-pass";
    document.getElementById("btn-start-benchmark").disabled = false;
    document.getElementById("btn-start-benchmark").textContent = "🚀 Launch 2MA-Bench Run";

    // Enable export buttons
    document.getElementById("btn-export-json").disabled = false;
    document.getElementById("btn-export-csv").disabled = false;
    document.getElementById("btn-export-md").disabled = false;

    // Update Metrics
    document.getElementById("metric-score").textContent = `${currentSummary.overall_score}%`;
    document.getElementById("metric-passrate").textContent = `${currentSummary.passed_count} / ${currentSummary.total_problems}`;
    document.getElementById("metric-tokens").textContent = currentSummary.total_tokens.toLocaleString();
    document.getElementById("metric-latency").textContent = `${Math.round(currentSummary.average_latency_ms)} ms`;

    // Update Radar Chart
    updateRadarChart(currentSummary.dimension_scores);

    // Make items inspectable
    makeItemsInspectable();
    if (eventSource) eventSource.close();
  } else if (event.type === "run_error") {
    alert("Evaluation Run Error: " + event.error);
    document.getElementById("run-status-badge").textContent = "ERROR";
    document.getElementById("run-status-badge").className = "badge tag-fail";
    document.getElementById("btn-start-benchmark").disabled = false;
    document.getElementById("btn-start-benchmark").textContent = "🚀 Launch 2MA-Bench Run";
    if (eventSource) eventSource.close();
  }
}

function makeItemsInspectable() {
  if (!currentSummary) return;
  currentSummary.results.forEach((r) => {
    const item = document.getElementById(`item-${r.problem_id}`);
    if (item) {
      item.style.cursor = "pointer";
      item.title = "Click to inspect prompt and model response";
      item.addEventListener("click", () => showDetailModal(r));
    }
  });
}

function showDetailModal(result) {
  const modal = document.getElementById("detail-modal");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");

  title.textContent = `${result.dimension_name}: ${result.title}`;
  
  let verificationInfo = `<p><strong>Status:</strong> <span class="${result.verification.passed ? 'tag-pass' : 'tag-fail'}">${result.verification.passed ? 'PASSED' : 'FAILED'}</span></p>`;
  if (result.verification.failure_reason) {
    verificationInfo += `<p style="margin-top: 0.5rem; color: var(--accent-red);"><strong>Failure Reason:</strong> ${result.verification.failure_reason}</p>`;
  }

  body.innerHTML = `
    ${verificationInfo}
    <h4 style="margin-top: 1rem; color: var(--text-muted);">Generated Challenge Prompt</h4>
    <pre>${escapeHtml(result.prompt)}</pre>
    <h4 style="margin-top: 1rem; color: var(--text-muted);">Model Output</h4>
    <pre>${escapeHtml(result.model_response.content)}</pre>
  `;

  modal.style.display = "flex";
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function exportJson() {
  if (!currentSummary) return;
  const blob = new Blob([JSON.stringify(currentSummary, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentSummary.run_id}_report.json`;
  a.click();
}

function exportCsv() {
  if (!currentRunId) return;
  window.open(`${getApiBaseUrl()}/api/export/${currentRunId}/csv`, "_blank");
}

function exportMarkdown() {
  if (!currentRunId) return;
  window.open(`${getApiBaseUrl()}/api/export/${currentRunId}/markdown`, "_blank");
}

async function openCompareModal() {
  const modal = document.getElementById("compare-modal");
  const selA = document.getElementById("compare-run-a");
  const selB = document.getElementById("compare-run-b");
  const diffView = document.getElementById("compare-diff-view");

  try {
    const res = await fetch(`${getApiBaseUrl()}/api/runs`);
    const runs = await res.json();
    if (!runs || runs.length < 2) {
      diffView.innerHTML = `<p style="color: var(--accent-amber); padding: 1rem;">Complete at least 2 benchmark runs first to compare models.</p>`;
      modal.style.display = "flex";
      return;
    }

    selA.innerHTML = "";
    selB.innerHTML = "";
    runs.forEach((r, idx) => {
      const optA = document.createElement("option");
      optA.value = r.run_id;
      optA.textContent = `${r.model} (${r.overall_score}%) - ${r.run_id}`;
      selA.appendChild(optA);

      const optB = document.createElement("option");
      optB.value = r.run_id;
      optB.textContent = `${r.model} (${r.overall_score}%) - ${r.run_id}`;
      if (idx === runs.length - 1) optB.selected = true;
      selB.appendChild(optB);
    });

    diffView.innerHTML = `<p style="color: var(--text-muted); padding: 1rem;">Select two runs above and click <strong>Compare</strong>.</p>`;
    modal.style.display = "flex";
  } catch (e) {
    alert("Failed to load run history: " + e.message);
  }
}

async function executeComparison() {
  const runA = document.getElementById("compare-run-a").value;
  const runB = document.getElementById("compare-run-b").value;
  const diffView = document.getElementById("compare-diff-view");

  if (!runA || !runB) return;
  if (runA === runB) {
    diffView.innerHTML = `<p style="color: var(--accent-amber); padding: 0.5rem;">Please select two different runs to compare.</p>`;
    return;
  }

  diffView.innerHTML = "<p style='color: var(--accent-cyan);'>Loading comparison matrix...</p>";
  try {
    const res = await fetch(`${getApiBaseUrl()}/api/compare?run_a=${runA}&run_b=${runB}`);
    const data = await res.json();

    let diffColor = data.score_diff > 0 ? "var(--accent-green)" : (data.score_diff < 0 ? "var(--accent-red)" : "#fff");
    let diffPrefix = data.score_diff > 0 ? "+" : "";

    let html = `
      <div style="background: rgba(0,0,0,0.4); padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border: 1px solid rgba(255,255,255,0.1);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong>${escapeHtml(data.run_a.model)}</strong>: <span style="color: var(--accent-cyan);">${data.run_a.overall_score}%</span>
            <span style="color: var(--text-muted); font-size: 0.75rem;">(${data.run_a.average_latency_ms}ms)</span>
          </div>
          <div style="font-size: 1.1rem; font-weight: bold; color: ${diffColor};">
            Δ ${diffPrefix}${data.score_diff}%
          </div>
          <div>
            <strong>${escapeHtml(data.run_b.model)}</strong>: <span style="color: var(--accent-purple);">${data.run_b.overall_score}%</span>
            <span style="color: var(--text-muted); font-size: 0.75rem;">(${data.run_b.average_latency_ms}ms)</span>
          </div>
        </div>
      </div>
      <table style="width: 100%; border-collapse: collapse; text-align: left;">
        <thead>
          <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted);">
            <th style="padding: 0.5rem;">Dimension</th>
            <th style="padding: 0.5rem; text-align: right;">${escapeHtml(data.run_a.model)}</th>
            <th style="padding: 0.5rem; text-align: right;">${escapeHtml(data.run_b.model)}</th>
            <th style="padding: 0.5rem; text-align: right;">Diff</th>
          </tr>
        </thead>
        <tbody>
    `;

    data.dimensions.forEach((d) => {
      const dColor = d.diff > 0 ? "var(--accent-green)" : (d.diff < 0 ? "var(--accent-red)" : "var(--text-muted)");
      const dPrefix = d.diff > 0 ? "+" : "";
      html += `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
          <td style="padding: 0.5rem;">${DIMENSION_LABELS[d.dimension] || d.dimension}</td>
          <td style="padding: 0.5rem; text-align: right;">${d.model_a_score}%</td>
          <td style="padding: 0.5rem; text-align: right;">${d.model_b_score}%</td>
          <td style="padding: 0.5rem; text-align: right; color: ${dColor}; font-weight: bold;">${dPrefix}${d.diff}%</td>
        </tr>
      `;
    });

    html += `</tbody></table>`;
    diffView.innerHTML = html;
  } catch (err) {
    diffView.innerHTML = `<p style="color: var(--accent-red);">Error loading comparison: ${err.message}</p>`;
  }
}
