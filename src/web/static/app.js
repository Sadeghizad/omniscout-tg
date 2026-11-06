/* OmniScout-TG dashboard: brief form, SSE pipeline progress, results table. */

const STAGES = [
  { n: "01", label: "Discovery", note: "live crawl" },
  { n: "02", label: "Validation", note: "live gate" },
  { n: "03", label: "Relevance", note: "BM25 + dense RAG" },
  { n: "04", label: "Triage", note: "persona + safety" },
  { n: "05", label: "Pricing", note: "CPM ceiling" },
  { n: "06", label: "Export", note: "xlsx + csv" },
];

const SORTS = {
  fit: ["Fit score", (a, b) => b.fit - a.fit],
  subscribers: ["Subscribers", (a, b) => b.subscribers - a.subscribers],
  reach: ["24h reach", (a, b) => b.reach_24h - a.reach_24h],
  ceiling: ["CPM ceiling", (a, b) => b.cpm_ceiling - a.cpm_ceiling],
  bid: ["Target bid", (a, b) => b.bid_target - a.bid_target],
  confidence: ["Confidence", (a, b) => b.confidence - a.confidence],
};

const $ = (id) => document.getElementById(id);
const form = $("brief-form");
const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v) => Number(v || 0).toLocaleString("en-US");
const money = (v) => `$${Number(v || 0).toFixed(2)}`;

let payload = null;
let filter = "ALL";
let sortKey = "fit";
let openRow = null;
let ticker = null;

/* ── Config and status ─────────────────────────────────────── */

async function loadConfig() {
  const cfg = await fetch("/api/config").then((r) => r.json());
  $("chip-bai").dataset.on = String(cfg.bai_live);
  $("chip-bai").title = cfg.bai_live
    ? "b.ai gateway key present: creative hooks are model-written."
    : "No b.ai key: creative hooks fall back to deterministic templates.";
  $("chip-mtproto").dataset.on = String(cfg.mtproto_enabled);
  $("chip-mtproto").title = cfg.mtproto_enabled
    ? "Telegram MTProto session configured: native recommendations available."
    : "No MTProto session: discovery uses the public web graph (this is fine).";
  $("chip-output").textContent = cfg.output_dir;

  const d = cfg.defaults;
  setValue("est_cvr", d.est_cvr);
  setValue("est_ctr_min", d.est_ctr_min);
  setValue("est_ctr_max", d.est_ctr_max);
  setValue("risk_buffer", d.risk_buffer);
  setValue("target_cac_usd", d.target_cac_usd);
  window.__preset = cfg.preset;

  const saved = localStorage.getItem("omniscout.brief");
  if (saved) {
    try {
      applyBrief(JSON.parse(saved));
    } catch {
      /* ignore a corrupt cache */
    }
  }
}

function setValue(name, value) {
  const el = form.elements[name];
  if (el && !el.value) el.value = value;
}

function applyBrief(brief) {
  for (const [key, value] of Object.entries(brief)) {
    const el = form.elements[key];
    if (!el) continue;
    el.value = Array.isArray(value) ? value.join(", ") : value;
  }
}

function readBrief() {
  const val = (name) => form.elements[name].value.trim();
  const seeds = val("seed_channels")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const m = s.match(/t\.me\/(?:s\/)?([\w\d_]+)/i);
      const handle = m ? m[1] : s.replace(/^@/, "");
      return `@${handle.toLowerCase()}`;
    });

  return {
    campaign_name: val("campaign_name"),
    product_category: val("product_category") || "Business",
    target_persona: val("target_persona"),
    seed_channels: seeds.length ? seeds : ["@parvazcapital_tel"],
    total_budget_usd: Number(val("total_budget_usd")) || 1000,
    target_cac_usd: Number(val("target_cac_usd")) || 50,
    est_cvr: Number(val("est_cvr")) || 0.02,
    est_ctr_min: Number(val("est_ctr_min")) || 0.01,
    est_ctr_max: Number(val("est_ctr_max")) || 0.025,
    risk_buffer: Number(val("risk_buffer")) || 0.15,
  };
}

/* ── Run lifecycle ─────────────────────────────────────────── */

function show(view) {
  for (const id of ["idle", "run", "results"]) $(id).hidden = id !== view;
}

function renderStages() {
  $("stages").innerHTML = STAGES.map(
    (s, i) =>
      `<li class="stage" data-state="pending" id="stage-${i}">
         <span class="n">${s.n}</span>
         <span class="label">${esc(s.label)} <span class="muted">· ${esc(s.note)}</span></span>
         <span class="state">queued</span>
         <div class="bar"></div>
       </li>`,
  ).join("");
}

function markStage(step, state) {
  const el = $("stage-" + (step - 1));
  if (!el) return;
  el.dataset.state = state;
  el.querySelector(".state").textContent =
    state === "done" ? "done" : state === "active" ? "running" : state === "failed" ? "failed" : "queued";
}

function logLine(step, message) {
  const log = $("log");
  const at = new Date().toLocaleTimeString("en-GB", { hour12: false });
  log.insertAdjacentHTML(
    "beforeend",
    `<div><b>${at}</b>  [${esc(step)}/6]  ${esc(message)}</div>`,
  );
  log.scrollTop = log.scrollHeight;
}

async function run(event) {
  event.preventDefault();

  const error = $("form-error");
  const brief = readBrief();
  const missing = ["campaign_name", "target_persona"].filter((k) => !brief[k]);
  if (missing.length) {
    error.textContent =
      missing[0] === "campaign_name"
        ? "Name the campaign before running."
        : "Describe who the ads must reach: the persona drives every relevance score.";
    error.hidden = false;
    form.elements[missing[0]].focus();
    return;
  }
  error.hidden = true;
  localStorage.setItem("omniscout.brief", JSON.stringify(brief));

  show("run");
  renderStages();
  $("log").innerHTML = "";
  openRow = null;
  payload = null;

  const button = $("run-btn");
  button.disabled = true;
  button.textContent = "Running…";
  $("run-title").textContent = brief.campaign_name;

  const started = Date.now();
  clearInterval(ticker);
  ticker = setInterval(() => {
    $("run-elapsed").textContent = `${Math.floor((Date.now() - started) / 1000)}s`;
  }, 1000);

  try {
    const response = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(brief),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `HTTP ${response.status}`);
    }
    await consume(response.body.getReader());
  } catch (err) {
    fail(err.message);
  } finally {
    clearInterval(ticker);
    button.disabled = false;
    button.textContent = "Run media plan";
  }
}

async function consume(reader) {
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let cut;
    while ((cut = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);

      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      handle(event, JSON.parse(data));
    }
  }
}

function handle(event, data) {
  if (event === "progress") {
    for (let i = 1; i < data.step; i += 1) {
      const prev = $("stage-" + (i - 1));
      if (prev && prev.dataset.state !== "done") markStage(i, "done");
    }
    markStage(data.step, "active");
    logLine(data.step, data.message);
  } else if (event === "result") {
    STAGES.forEach((_, i) => markStage(i + 1, "done"));
    logLine(6, "Deliverables written.");
    payload = data;
    render(data);
  } else if (event === "error") {
    fail(data.message);
  }
}

function fail(message) {
  const active = document.querySelector('.stage[data-state="active"]');
  if (active) active.dataset.state = "failed";
  logLine(0, `Failed: ${message}`);
  $("run-title").textContent = "Run failed";
  const error = $("form-error");
  error.textContent = message;
  error.hidden = false;
  console.error(message);
}

/* ── Results ───────────────────────────────────────────────── */

function render(data) {
  const summary = data.summary;
  const campaign = data.campaign;

  $("results-title").textContent = campaign.name;
  $("results-sub").textContent = [
    campaign.category,
    `${money(campaign.budget_usd)} budget`,
    `${money(campaign.target_cac_usd)} CAC`,
    `seeds ${campaign.seed_channels.join(" ")}`,
  ].join("   ·   ");

  $("downloads").innerHTML = [
    ["xlsx", data.files.xlsx, "Excel workbook · 8 sheets"],
    ["csv", data.files.csv, "CSV · UTF-8"],
  ]
    .map(
      ([kind, name, title]) => `<a class="dl" href="/api/files/${encodeURIComponent(name)}" download title="${esc(title)}">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0 3-3M8 10 5 7M3 13h10" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <b>${esc(name)}</b>
        </a>`,
    )
    .join("");

  const kpis = [
    ["Discovered", num(summary.total_discovered)],
    ["Passed triage", num(summary.passed_triage)],
    ["Buy cells", num(summary.approved_buy_count)],
    ["Test cells", num(summary.test_cell_count)],
    ["Reach 24h", num(summary.total_qualified_reach)],
    ["Est. leads", num(summary.est_leads)],
    ["Avg target bid", money(summary.avg_target_bid_cpm)],
  ];
  $("kpis").innerHTML = kpis
    .map(([label, value]) => `<div class="kpi"><dt>${esc(label)}</dt><dd>${value}</dd></div>`)
    .join("");

  renderFilters(data.channels);
  $("sort").innerHTML = Object.entries(SORTS)
    .map(([key, [label]]) => `<option value="${key}"${key === sortKey ? " selected" : ""}>${esc(label)}</option>`)
    .join("");

  show("results");
  $("results").dataset.state = "ready";
  renderTable();
}

function renderFilters(rows) {
  const counts = rows.reduce((acc, row) => {
    acc[row.recommendation] = (acc[row.recommendation] || 0) + 1;
    return acc;
  }, {});
  const keys = ["ALL", ...Object.keys(counts).sort()];

  $("filters").innerHTML = keys
    .map(
      (key) =>
        `<button type="button" data-k="${esc(key)}" aria-pressed="${key === filter}">
           ${key === "ALL" ? "All channels" : esc(key.replace(/_/g, " "))}
           <span>${key === "ALL" ? rows.length : counts[key]}</span>
         </button>`,
    )
    .join("");
}

function renderTable() {
  if (!payload) return;
  const rows = payload.channels
    .filter((row) => filter === "ALL" || row.recommendation === filter)
    .sort(SORTS[sortKey][1]);

  $("tbody").innerHTML = rows
    .map((row, index) => {
      const ratio = row.cpm_ceiling > 0 ? Math.round((row.bid_target / row.cpm_ceiling) * 100) : 0;
      const detail =
        openRow === row.id
          ? `<tr class="detail"><td colspan="9"><dl class="detail-grid">
               <div><dt>Validation</dt><dd class="mono">${esc(row.validation_status)}</dd></div>
               <div><dt>Depth / source</dt><dd class="mono">d${row.depth} · ${esc(row.source)}</dd></div>
               <div><dt>Confidence</dt><dd class="mono">${row.confidence.toFixed(0)} / 100</dd></div>
               <div><dt>Est. leads / 1k</dt><dd class="mono">${row.est_leads}</dd></div>
               <div><dt>ICP score</dt><dd class="mono">${row.icp_score} / 5</dd></div>
               <div><dt>BM25 / dense</dt><dd class="mono">${row.bm25.toFixed(2)} · ${row.dense.toFixed(2)}</dd></div>
               <div class="wide"><dt>Operator caveat</dt><dd>${esc(row.validation_caveat || "None recorded.")}</dd></div>
               ${row.seed_parent ? `<div class="wide"><dt>Discovered from</dt><dd class="mono">${esc(row.seed_parent)}</dd></div>` : ""}
             </dl></td></tr>`
          : "";

      return `<tr class="row" data-id="${esc(row.id)}" tabindex="0" style="--i:${Math.min(index, 20)}">
          <td class="col-channel">
            <span class="ch-id">${esc(row.id)}</span>
            <span class="ch-title" title="${esc(row.title)}">${esc(row.title)}</span>
          </td>
          <td class="num">${num(row.subscribers)}</td>
          <td class="num">${num(row.reach_24h)}</td>
          <td class="num">${row.err24.toFixed(2)}<span class="muted">%</span></td>
          <td class="num">${row.fit.toFixed(0)}</td>
          <td class="num">${row.cpm_ceiling.toFixed(2)}</td>
          <td class="num">${row.bid_target.toFixed(2)}</td>
          <td class="num">
            <div class="meter">
              <span class="track"><span class="fill" data-k="${esc(row.recommendation)}" style="width:${ratio}%"></span></span>
              <output>${ratio}%</output>
            </div>
          </td>
          <td><span class="pill" data-k="${esc(row.recommendation)}">${esc(row.recommendation.replace(/_/g, " "))}</span></td>
        </tr>${detail}`;
    })
    .join("");

  $("table-empty").hidden = rows.length > 0;
  $("table").hidden = rows.length === 0;
}

/* ── Wiring ────────────────────────────────────────────────── */

form.addEventListener("submit", run);

$("preset-btn").addEventListener("click", () => {
  if (window.__preset) applyBrief(window.__preset);
});

$("filters").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-k]");
  if (!button) return;
  filter = button.dataset.k;
  for (const b of $("filters").children) b.setAttribute("aria-pressed", String(b === button));
  renderTable();
});

$("sort").addEventListener("change", (event) => {
  sortKey = event.target.value;
  renderTable();
});

$("tbody").addEventListener("click", (event) => {
  const row = event.target.closest("tr.row");
  if (!row) return;
  openRow = openRow === row.dataset.id ? null : row.dataset.id;
  renderTable();
});

$("tbody").addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest("tr.row");
  if (!row) return;
  event.preventDefault();
  openRow = openRow === row.dataset.id ? null : row.dataset.id;
  renderTable();
  document.querySelector(`tr.row[data-id="${CSS.escape(openRow)}"]`)?.focus();
});

loadConfig().catch((err) => {
  $("status").innerHTML = `<span class="chip" data-on="false"><i class="dot"></i>backend unreachable</span>`;
  console.error(err);
});
