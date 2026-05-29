"use strict";

const PHONE_W = 1080, PHONE_H = 2400;
const SCREEN_W = 292, SCREEN_H = 612; // inner screen px (phone padding accounted)

const el = (id) => document.getElementById(id);
let mode = "collaborative";
let trace = null;
let cursor = 0;          // how many steps revealed
let awaitingAuth = false;

// ---- init -----------------------------------------------------------------
async function init() {
  const res = await fetch("/api/scenarios");
  const data = await res.json();
  const sel = el("scenario");
  data.scenarios.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.title;
    sel.appendChild(opt);
  });
  updateNote();

  sel.addEventListener("change", updateNote);
  el("mode-toggle").addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") return;
    mode = e.target.dataset.mode;
    document.querySelectorAll("#mode-toggle button").forEach((b) =>
      b.classList.toggle("active", b.dataset.mode === mode));
  });
  el("run").addEventListener("click", loadFlow);
  el("next").addEventListener("click", stepForward);
  el("authorize").addEventListener("click", authorize);
}

function updateNote() {
  const sel = el("scenario");
  const opt = sel.options[sel.selectedIndex];
  el("scenario-note").textContent = "";
  fetch("/api/scenarios").then((r) => r.json()).then((d) => {
    const s = d.scenarios.find((x) => x.id === sel.value);
    if (s) el("scenario-note").textContent = "Goal: " + s.expected;
  });
}

// ---- load + reset ---------------------------------------------------------
async function loadFlow() {
  const scenario = el("scenario").value;
  const res = await fetch(`/api/run?scenario=${scenario}&mode=${mode}`);
  trace = await res.json();
  cursor = 0;
  awaitingAuth = false;

  el("payload").textContent = "// press Step ▸ to run the agent on screen 1";
  el("thought").textContent = "";
  el("safety").innerHTML = "";
  el("payload-count").textContent = "—";
  el("payload-count").classList.remove("hot");
  el("knows").innerHTML = '<li class="muted">Nothing yet.</li>';
  el("knows-summary").textContent = "";
  setBar("exp", 0); setBar("cum", 0); setBar("sens", 0);

  renderScreen(trace.steps[0].screen, null);
  el("step-label").textContent = `0 / ${trace.steps.length} steps`;
  el("next").disabled = false;
  el("next").textContent = "Step ▸";
  el("authorize").classList.add("hidden");
}

// ---- step through ---------------------------------------------------------
function stepForward() {
  if (!trace || cursor >= trace.steps.length) return;
  const step = trace.steps[cursor];

  renderScreen(step.screen, step);
  el("thought").textContent = "💭 " + step.thought;
  renderSafety(step.safety);
  renderPayload(step);
  updateMeters();
  updateKnowledge();

  el("step-label").textContent = `${cursor + 1} / ${trace.steps.length} steps`;

  if (step.safety.verdict === "block") {
    el("next").disabled = true;
    el("authorize").classList.add("hidden");
    el("step-label").textContent += " — BLOCKED";
    cursor++;
    return;
  }
  if (step.safety.verdict === "require_confirmation") {
    awaitingAuth = true;
    el("next").disabled = true;
    el("authorize").classList.remove("hidden");
    return;
  }
  // allow -> advance
  cursor++;
  finishIfDone();
}

function authorize() {
  awaitingAuth = false;
  el("authorize").classList.add("hidden");
  el("next").disabled = false;
  cursor++;
  finishIfDone();
}

function finishIfDone() {
  if (cursor >= trace.steps.length) {
    el("next").disabled = true;
    el("step-label").textContent += " — ✓ completed";
  }
}

// ---- rendering ------------------------------------------------------------
function renderScreen(screen, step) {
  const root = el("screen");
  root.innerHTML = "";
  const uploaded = step ? new Set(step.uploaded.payload.map((p) => p.id)) : new Set();
  const targetId = step ? step.decision.element_id : null;

  screen.elements.forEach((e) => {
    if (e.id === "root") return;
    const [x1, y1, x2, y2] = e.bounds;
    if (e.role === "LinearLayout" || e.role === "FrameLayout") return; // containers invisible
    const node = document.createElement("div");
    let cls = "node";
    if (e.id === "title") cls += " title";
    else if (e.role === "input") cls += " input";
    else if (e.role === "button" && e.id === "nav_home") cls += " nav";
    else if (e.role === "button") cls += " button";
    else cls += " text";
    if (e.sensitive) cls += " sensitive";
    if (e.id === targetId) cls += " target";
    if (uploaded.has(e.id)) cls += " uploaded";
    node.className = cls;
    node.style.left = (x1 / PHONE_W * SCREEN_W) + "px";
    node.style.top = (y1 / PHONE_H * SCREEN_H) + "px";
    node.style.width = ((x2 - x1) / PHONE_W * SCREEN_W) + "px";
    node.style.height = ((y2 - y1) / PHONE_H * SCREEN_H) + "px";
    node.textContent = e.text || e.description || "";
    root.appendChild(node);
  });
}

function renderSafety(safety) {
  const labels = {
    allow: "✓ ALLOW", require_confirmation: "⏸ NEEDS CONFIRMATION", block: "⛔ BLOCKED",
  };
  el("safety").innerHTML =
    `<span class="badge ${safety.verdict}">${labels[safety.verdict]}</span>` +
    `<div class="reason">${safety.reason}</div>`;
}

function renderPayload(step) {
  const n = step.uploaded.count, total = step.uploaded.total;
  const countEl = el("payload-count");
  countEl.textContent = `${n} / ${total} elements`;
  countEl.classList.toggle("hot", n / total > 0.5);

  const lines = step.uploaded.payload.map((p) => {
    const text = p.text === "[MASKED_SENSITIVE]"
      ? `<span class="masked">"[MASKED_SENSITIVE]"</span>`
      : JSON.stringify(p.text);
    return `  { "id": <span class="rid">"${p.id}"</span>, "role": "${p.role}", "text": ${text} }`;
  });
  el("payload").innerHTML = "[\n" + lines.join(",\n") + "\n]";
}

function setBar(name, pct) {
  el(name + "-bar").style.width = Math.round(pct * 100) + "%";
  el(name + "-val").textContent = Math.round(pct * 100) + "%";
}

function updateMeters() {
  const revealed = trace.steps.slice(0, cursor + 1);
  const step = trace.steps[cursor];
  setBar("exp", step.exposure_rate);

  // cumulative over revealed steps (union by screen:id)
  const seen = new Set(), seenSens = new Set(), up = new Set(), upSens = new Set();
  revealed.forEach((s) => {
    s.screen.elements.forEach((e) => {
      if (e.role === "LinearLayout" || e.role === "FrameLayout") return;
      seen.add(s.screen.id + ":" + e.id);
      if (e.sensitive) seenSens.add(s.screen.id + ":" + e.id);
    });
    s.uploaded.payload.forEach((p) => {
      up.add(s.screen.id + ":" + p.id);
      if (p.text === "[MASKED_SENSITIVE]") upSens.add(s.screen.id + ":" + p.id);
    });
  });
  setBar("cum", seen.size ? up.size / seen.size : 0);
  setBar("sens", seenSens.size ? upSens.size / seenSens.size : 0);
}

function updateKnowledge() {
  const revealed = trace.steps.slice(0, cursor + 1);
  const items = [];
  revealed.forEach((s) => (s.cloud_sees_sensitive || []).forEach((t) => items.push(t)));
  const list = el("knows");
  if (items.length === 0) {
    list.innerHTML = '<li class="muted">✓ No sensitive data transmitted to the cloud.</li>';
  } else {
    const uniq = [...new Set(items)];
    list.innerHTML = uniq.map((t) => `<li>${escapeHtml(t)}</li>`).join("");
  }
  el("knows-summary").textContent = trace.cloud_knowledge.summary;
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

init();
