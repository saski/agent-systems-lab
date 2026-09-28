(() => {
  "use strict";

  const POLL_MS = 1000;
  const MAX_EVENTS = 300;
  const stageOrder = ["researcher", "builder", "reviewer", "validate", "human_review", "completed"];
  const stageNames = {
    researcher: "Researcher", builder: "Builder", reviewer: "Reviewer",
    validate: "Validate", human_review: "Human review", completed: "Completed",
    revoked: "Revoked", unknown: "Unknown"
  };
  const state = {
    token: "", cursor: 0, head: null, events: [], sequences: new Set(), runs: [], selectedRunId: null,
    selectedRunEvents: null, selectedRunEventsFor: null, runRequest: 0,
    integrity: null, telemetry: null, connected: false, stale: false, stopped: false,
    firstSnapshot: true, lastPoll: null, generation: 0, pollTimer: null,
    pollController: null, runController: null
  };
  const $ = (selector, root = document) => root.querySelector(selector);

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
  }

  function setText(selector, value) {
    const item = $(selector);
    if (item) item.textContent = value;
  }

  function formatTime(value, withDate = false) {
    if (!value) return "Time unavailable";
    const date = parseDate(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, withDate
      ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
      : { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
  }

  function elapsed(value) {
    if (!value) return "Time unavailable";
    const date = parseDate(value).getTime();
    if (!Number.isFinite(date)) return "Time unavailable";
    const seconds = Math.max(0, Math.floor((Date.now() - date) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }

  function parseDate(value) {
    if (typeof value === "number") return new Date(value < 100000000000 ? value * 1000 : value);
    if (typeof value === "string" && /^\d{10}(?:\.\d+)?$/.test(value)) return new Date(Number(value) * 1000);
    return new Date(value);
  }

  function isFresh(value, maxAgeSeconds) {
    const timestamp = parseDate(value).getTime();
    const age = Date.now() - timestamp;
    return Number.isFinite(timestamp) && age >= -5000 && age <= maxAgeSeconds * 1000;
  }

  function compactId(value, length = 15) {
    if (!value) return "Unavailable";
    const text = String(value);
    return text.length > length ? `${text.slice(0, length)}…` : text;
  }

  function titleCase(value) {
    return String(value || "unknown").replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
  }

  function setConnection(kind, label) {
    const badge = $("#connection");
    badge.dataset.state = kind;
    badge.lastElementChild.textContent = label;
    const feed = $("#feed-badge");
    feed.dataset.state = kind;
    feed.lastChild.textContent = kind === "connected" ? " LIVE FEED" : kind === "stale" ? " STALE FEED" : " FEED IDLE";
    $("#stale-banner").classList.toggle("hidden", kind !== "stale");
    state.connected = kind === "connected";
    state.stale = kind === "stale";
    updateTopology();
  }

  function showAuthError(message) {
    setText("#auth-error", message || "");
  }

  function connect(token) {
    state.generation += 1;
    clearTimeout(state.pollTimer);
    state.pollController?.abort();
    state.runController?.abort();
    state.pollController = null;
    state.runController = null;
    state.token = token;
    state.stopped = false;
    state.cursor = 0;
    state.head = null;
    state.events = [];
    state.sequences.clear();
    state.runs = [];
    state.selectedRunId = null;
    state.selectedRunEvents = null;
    state.selectedRunEventsFor = null;
    state.runRequest += 1;
    state.integrity = null;
    state.telemetry = null;
    state.firstSnapshot = true;
    $("#auth-gate").classList.add("hidden");
    $("#dashboard").classList.remove("hidden");
    $("#logout").classList.remove("hidden");
    showAuthError("");
    $("#token").value = "";
    setConnection("connecting", "Connecting");
    poll(state.generation);
  }

  function lockViewer() {
    state.generation += 1;
    clearTimeout(state.pollTimer);
    state.pollController?.abort();
    state.runController?.abort();
    state.pollController = null;
    state.runController = null;
    state.stopped = true;
    state.token = "";
    state.cursor = 0;
    state.head = null;
    state.events = [];
    state.sequences.clear();
    state.runs = [];
    state.selectedRunId = null;
    state.selectedRunEvents = null;
    state.selectedRunEventsFor = null;
    state.runRequest += 1;
    state.integrity = null;
    state.telemetry = null;
    $("#token").value = "";
    $("#dashboard").classList.add("hidden");
    $("#logout").classList.add("hidden");
    $("#auth-gate").classList.remove("hidden");
    setConnection("offline", "Disconnected");
    render();
  }

  async function poll(generation) {
    if (state.stopped || !state.token) return;
    let hasMore = false;
    const controller = new AbortController();
    state.pollController = controller;
    try {
      const response = await fetch(`/api/activity?after=${encodeURIComponent(state.cursor)}`, {
        method: "GET", cache: "no-store",
        headers: { Authorization: `Bearer ${state.token}`, Accept: "application/json" },
        signal: controller.signal
      });
      if (generation !== state.generation || state.stopped || !state.token) return;
      if (response.status === 401) {
        handleUnauthorized(generation);
        return;
      }
      if (!response.ok) throw new Error(`Gateway returned HTTP ${response.status}`);
      const payload = await response.json();
      applySnapshot(payload);
      setConnection("connected", "Connected");
      state.lastPoll = new Date();
      hasMore = payload.has_more === true;
      render();
      setText("#updated-at", `Updated ${formatTime(state.lastPoll)}`);
    } catch (error) {
      if (generation !== state.generation || state.stopped || error.name === "AbortError") return;
      console.warn("Activity feed unavailable", error);
      setConnection("stale", "Reconnecting");
      render();
    } finally {
      if (state.pollController === controller) state.pollController = null;
      if (generation === state.generation && !state.stopped && state.token) {
        state.pollTimer = window.setTimeout(() => poll(generation), hasMore ? 0 : POLL_MS);
      }
    }
  }

  function applySnapshot(payload) {
    if (!payload || !Array.isArray(payload.events) || !Array.isArray(payload.runs)) {
      throw new Error("Gateway activity response has an unexpected shape");
    }
    for (const event of payload.events) {
      if (typeof event.sequence !== "number" || state.sequences.has(event.sequence)) continue;
      state.sequences.add(event.sequence);
      state.events.push(event);
    }
    state.events.sort((a, b) => a.sequence - b.sequence);
    if (state.events.length > MAX_EVENTS) {
      const removed = state.events.splice(0, state.events.length - MAX_EVENTS);
      for (const event of removed) state.sequences.delete(event.sequence);
    }
    if (typeof payload.cursor === "number") state.cursor = Math.max(state.cursor, payload.cursor);
    else if (payload.events.length) state.cursor = Math.max(state.cursor, ...payload.events.map(event => event.sequence));
    if (typeof payload.head === "number") state.head = payload.head;
    state.runs = payload.runs.slice(0, 100);
    state.integrity = payload.integrity || null;
    state.telemetry = payload.telemetry || null;
    if (!state.selectedRunId || !state.runs.some(run => run.run_id === state.selectedRunId)) {
      state.selectedRunId = state.runs[0]?.run_id || null;
      state.selectedRunEvents = null;
      state.selectedRunEventsFor = null;
      if (state.selectedRunId) loadRunEvents(state.selectedRunId);
    }
    if (state.selectedRunEvents && state.selectedRunEventsFor === state.selectedRunId) {
      mergeRunEvents(state.events.filter(event => event.run_id === state.selectedRunId));
    }
    state.firstSnapshot = false;
  }

  function tone(element, className) {
    element.classList.remove("tone-good", "tone-warn", "tone-bad", "tone-unknown");
    element.classList.add(className);
  }

  function renderMetrics() {
    const active = state.runs.filter(run => run.status === "running").length;
    setText("#metric-active", state.runs.length ? active : "0");
    setText("#metric-active-note", state.runs.length ? `${state.runs.length} recent run${state.runs.length === 1 ? "" : "s"} in view` : "No runs reported");
    setText("#run-count", active);
    setText("#runs-total", state.runs.length);

    const integrity = state.integrity;
    const integrityValue = $("#metric-integrity");
    integrityValue.textContent = integrity && typeof integrity.valid === "boolean" ? (integrity.valid ? "Verified" : "Mismatch") : "Unknown";
    tone(integrityValue, !integrity || typeof integrity.valid !== "boolean" ? "tone-unknown" : integrity.valid ? "tone-good" : "tone-bad");
    setText("#metric-integrity-note", integrity ? `${Number(integrity.checked) || 0} events checked · chain check only` : "No verification received");
    setText("#integrity-caption", "");
    const caption = $("#integrity-caption");
    const captionIcon = node("span", "caption-icon", integrity?.valid === true ? "✓" : integrity?.valid === false ? "!" : "◇");
    const captionText = node("span", "", integrity?.valid === true
      ? `Hash chain verified across ${Number(integrity.checked) || 0} events. Verification does not provide WORM storage.`
      : integrity?.valid === false
        ? `Ledger integrity mismatch after ${Number(integrity.checked) || 0} checked events. Hash-chain verification does not provide WORM storage.`
        : "Ledger verification pending. Hash-chain validation checks event linkage; it does not provide WORM storage.");
    caption.replaceChildren(captionIcon, captionText);
    captionIcon.classList.toggle("tone-bad", integrity?.valid === false);

    const telemetry = state.telemetry;
    const otlpValue = $("#metric-otlp");
    const pending = telemetry && Number.isFinite(Number(telemetry.pending)) ? Number(telemetry.pending) : null;
    if (!telemetry || typeof telemetry.enabled !== "boolean") {
      otlpValue.textContent = "Unknown"; tone(otlpValue, "tone-unknown");
      setText("#metric-otlp-note", "Waiting for telemetry state");
      setText("#otlp-label", "delivery unknown");
    } else if (!telemetry.enabled) {
      otlpValue.textContent = "Disabled"; tone(otlpValue, "tone-unknown");
      setText("#metric-otlp-note", "Exporter is disabled");
      setText("#otlp-label", "export disabled");
    } else if (telemetry.last_error) {
      otlpValue.textContent = "Delivery error"; tone(otlpValue, "tone-bad");
      setText("#metric-otlp-note", pending === null ? String(telemetry.last_error) : `${pending} pending · latest delivery failed`);
      setText("#otlp-label", "delivery error");
    } else if (pending > 0) {
      otlpValue.textContent = "Pending"; tone(otlpValue, "tone-warn");
      setText("#metric-otlp-note", `${pending} event${pending === 1 ? "" : "s"} awaiting delivery`);
      setText("#otlp-label", `${pending} pending`);
    } else {
      otlpValue.textContent = "Enabled"; tone(otlpValue, "tone-good");
      setText("#metric-otlp-note", telemetry.last_error ? "Latest delivery failed" : "No delivery pending");
      setText("#otlp-label", "delivery clear");
    }
    setText("#metric-events", integrity && Number.isFinite(Number(integrity.checked)) ? Number(integrity.checked).toLocaleString() : "—");
    setText("#metric-head", integrity?.head_hash ? `Head ${compactId(integrity.head_hash, 18)}` : "Ledger head unavailable");
    setText("#footer-cursor", `Cursor ${state.cursor.toLocaleString()} · head ${state.head === null ? "—" : state.head.toLocaleString()}`);
    if (state.runs.length || integrity || telemetry) setText("#map-state", `${active} active run${active === 1 ? "" : "s"} · gateway reported`);
  }

  function normalizedStatus(status) {
    return String(status || "unknown").toLowerCase().replaceAll(" ", "_");
  }

  function renderRuns() {
    const host = $("#runs-list");
    if (!state.runs.length) {
      host.replaceChildren(node("div", "empty-inline", "No runs reported by the gateway."));
      return;
    }
    const rows = state.runs.map(run => {
      const row = node("div", `run-row${run.run_id === state.selectedRunId ? " selected" : ""}`);
      row.tabIndex = 0;
      row.setAttribute("role", "button");
      row.setAttribute("aria-label", `Inspect run ${run.run_id}, ${titleCase(run.status)}, stage ${stageNames[run.stage] || stageNames.unknown}`);
      row.setAttribute("aria-pressed", String(run.run_id === state.selectedRunId));
      const identity = node("div", "run-identity");
      identity.append(node("div", "run-id", compactId(run.run_id, 23)), node("span", "run-stage", stageNames[run.stage] || stageNames.unknown));
      const badge = node("span", "status-badge", titleCase(run.status));
      badge.dataset.status = normalizedStatus(run.status);
      row.append(identity, badge, node("span", "run-age", elapsed(run.last_activity || run.created_at)));
      row.addEventListener("click", () => selectRun(run.run_id));
      row.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); selectRun(run.run_id); }
      });
      return row;
    });
    host.replaceChildren(...rows);
  }

  function stageProgress(stage, status) {
    const normalized = stageNames[stage] ? stage : "unknown";
    if (["revoked", "unknown"].includes(normalized)) return { normalized, active: -1, terminal: normalized };
    if (["accepted", "completed"].includes(status)) return { normalized: "completed", active: stageOrder.length - 1, terminal: "completed" };
    if (["rejected", "failed", "timed_out"].includes(status)) return { normalized, active: stageOrder.indexOf(normalized), terminal: status };
    return { normalized, active: stageOrder.indexOf(normalized), terminal: null };
  }

  function renderSelectedRun() {
    const run = state.runs.find(item => item.run_id === state.selectedRunId);
    const host = $("#run-detail");
    const mode = $("#run-mode");
    if (!run) {
      mode.textContent = "NO RUN"; mode.className = "mode-badge";
      host.replaceChildren();
      const empty = node("div", "empty-detail");
      empty.append(node("span", "", "◎"), node("strong", "", "No run selected"), node("small", "", "New runs will appear here when activity arrives."));
      host.append(empty);
      return;
    }
    const status = normalizedStatus(run.status);
    const fresh = isFresh(run.last_activity, 120);
    const isLive = status === "running" && state.connected && fresh;
    mode.textContent = state.stale ? "STALE SNAPSHOT"
      : isLive ? "LIVE"
        : status === "awaiting_review" ? "WAITING"
          : status === "running" ? "UNKNOWN" : "HISTORY";
    mode.className = `mode-badge${isLive ? "" : " historical"}`;
    host.replaceChildren();
    host.append(node("div", "detail-id", run.run_id));
    const statusLine = node("div", "detail-statusline");
    const badge = node("span", "status-badge", titleCase(run.status)); badge.dataset.status = status;
    statusLine.append(badge, node("span", "subtle-label", run.model_mode ? `${titleCase(run.model_mode)} mode` : "Model mode unknown"));
    host.append(statusLine);

    const meta = node("div", "detail-meta");
    const fields = [
      ["CURRENT STAGE", stageNames[run.stage] || stageNames.unknown],
      ["CREATED", formatTime(run.created_at, true)],
      ["LAST ACTIVITY", run.last_activity ? elapsed(run.last_activity) : "Unavailable"],
      ["TRACE ID", run.trace_id || "Unavailable"]
    ];
    for (const [label, value] of fields) {
      const field = node("div", "meta-item"); field.append(node("span", "", label), node("strong", "", value)); meta.append(field);
    }
    host.append(meta);

    const progress = stageProgress(run.stage, status);
    const title = node("div", "stage-title");
    title.append(node("span", "", "Workflow stages"), node("span", "", progress.terminal === "revoked" ? "Revoked" : progress.terminal && progress.terminal !== "completed" ? titleCase(progress.terminal) : ""));
    host.append(title);
    const steps = node("div", "stage-list");
    const agentsByRole = new Map((run.agents || []).map(agent => [agent.role, agent]));
    for (const [index, stage] of stageOrder.entries()) {
      const step = node("div", "stage-step", stageNames[stage]);
      if (progress.terminal === "revoked" || progress.normalized === "unknown") step.classList.add("unknown");
      else if (index < progress.active || (status === "accepted" || status === "completed")) step.classList.add("done");
      else if (index === progress.active) step.classList.add(progress.terminal ? "terminal" : "current");
      else if (["rejected", "failed", "timed_out"].includes(status) && index === progress.active) step.classList.add("terminal");
      const agent = agentsByRole.get(stage);
      if (agent?.status === "completed") step.classList.add("done");
      if (agent?.status === "running") step.classList.add("current");
      steps.append(step);
    }
    host.append(steps);
    const trace = node("div", "trace-line");
    trace.append(node("span", "", `Run ${compactId(run.run_id, 20)}`), node("code", "", run.trace_id ? `trace ${run.trace_id}` : "Trace unavailable"));
    host.append(trace);
  }

  function readableAction(event) {
    const action = String(event.action || "activity").replaceAll(".", "_").replaceAll("-", "_");
    const names = {
      run_create: "Run created", run_created: "Run created", run_started: "Run started", run_completed: "Run completed",
      run_failed: "Run failed", run_revoke: "Run revoked", run_revoked: "Run revoked", run_ready: "Run ready",
      run_decision: "Review decision recorded", grant_issue: "Scoped access issued", worker_started: "Agent started",
      worker_completed: "Agent completed", worker_failed: "Agent failed", worker_timed_out: "Agent timed out",
      agent_completed: "Agent completed", agent_failed: "Agent failed", tool_call: "Tool call",
      tool_result: "Tool result", access_granted: "Access granted", access_denied: "Access denied",
      decision_requested: "Human review requested", decision_accepted: "Review accepted",
      decision_rejected: "Review rejected", artifact_record: "Artifact recorded", artifact_written: "Artifact recorded",
      simulation_run: "Simulation executed", simulation_review: "Simulation reviewed", system_describe: "System described",
      model_call: "Model call", validate: "Validation"
    };
    return names[action] || titleCase(action);
  }

  function outcomeFor(event) {
    const value = normalizedStatus(event.decision);
    return ["deny", "denied", "rejected", "failed", "revoked", "error", "timed_out"].includes(value) ? value
      : ["allow", "allowed", "approved", "accepted", "completed"].includes(value) ? value : "neutral";
  }

  function renderEvents() {
    const host = $("#event-list");
    const selectedEvents = state.selectedRunEventsFor === state.selectedRunId ? state.selectedRunEvents : null;
    const sourceEvents = selectedEvents || (state.selectedRunId
      ? state.events.filter(event => event.run_id === state.selectedRunId)
      : state.events);
    const visible = sourceEvents.slice().reverse().slice(0, 45);
    setText("#event-count", `${sourceEvents.length} event${sourceEvents.length === 1 ? "" : "s"}${selectedEvents ? " · full run" : ""}`);
    if (!visible.length) {
      host.replaceChildren(node("div", "empty-inline", "Events will appear as the ledger advances."));
      return;
    }
    const rows = visible.map(event => {
      const outcome = outcomeFor(event);
      const row = node("article", "event-row"); row.dataset.outcome = outcome;
      const glyph = ["deny", "denied", "rejected", "failed", "revoked", "error", "timed_out"].includes(outcome) ? "!"
        : ["allow", "allowed", "approved", "accepted", "completed"].includes(outcome) ? "✓" : "↗";
      row.append(node("span", "event-marker", glyph));
      const body = node("div", "event-body");
      const top = node("div", "event-top");
      top.append(node("span", "event-title", readableAction(event)), node("time", "event-time", formatTime(event.timestamp)));
      body.append(top);
      const actor = event.actor ? titleCase(event.actor) : "System";
      const decision = event.decision ? ` · ${titleCase(event.decision)}` : "";
      body.append(node("div", "event-summary", `${actor}${event.run_id ? ` · ${compactId(event.run_id, 18)}` : ""}${decision}`));
      if (event.detail || event.hash || event.trace_id || event.span_id) {
        const extra = node("div", "event-extra");
        if (event.detail) extra.append(node("div", "", String(event.detail)));
        const codes = [];
        if (event.trace_id) codes.push(["trace", event.trace_id]);
        if (event.span_id) codes.push(["span", event.span_id]);
        if (event.previous_hash) codes.push(["prev", event.previous_hash]);
        if (event.hash) codes.push(["hash", event.hash]);
        for (const [label, value] of codes) {
          const line = node("div"); line.append(node("span", "", `${label} `), node("code", "", value)); extra.append(line);
        }
        body.append(extra);
      }
      row.append(body);
      return row;
    });
    host.replaceChildren(...rows);
  }

  function selectRun(runId) {
    if (state.selectedRunId === runId) return;
    state.selectedRunId = runId;
    state.runController?.abort();
    state.runController = null;
    state.selectedRunEvents = null;
    state.selectedRunEventsFor = null;
    renderRuns();
    renderSelectedRun();
    renderEvents();
    updateTopology();
    loadRunEvents(runId);
  }

  function mergeRunEvents(events) {
    const bySequence = new Map((state.selectedRunEvents || []).map(event => [event.sequence, event]));
    for (const event of events) if (typeof event.sequence === "number") bySequence.set(event.sequence, event);
    state.selectedRunEvents = Array.from(bySequence.values()).sort((a, b) => a.sequence - b.sequence);
  }

  async function loadRunEvents(runId) {
    if (!runId || !state.token || state.stopped) return;
    const request = ++state.runRequest;
    const generation = state.generation;
    const controller = new AbortController();
    state.runController?.abort();
    state.runController = controller;
    try {
      const response = await fetch(`/api/activity/${encodeURIComponent(runId)}`, {
        method: "GET", cache: "no-store",
        headers: { Authorization: `Bearer ${state.token}`, Accept: "application/json" },
        signal: controller.signal
      });
      if (generation !== state.generation || request !== state.runRequest || state.stopped) return;
      if (response.status === 401) { handleUnauthorized(generation); return; }
      if (!response.ok) throw new Error(`Gateway returned HTTP ${response.status}`);
      const payload = await response.json();
      if (state.stopped || request !== state.runRequest || state.selectedRunId !== runId) return;
      if (!Array.isArray(payload.events)) throw new Error("Run activity response has an unexpected shape");
      state.selectedRunEvents = payload.events.filter(event => typeof event.sequence === "number");
      state.selectedRunEventsFor = runId;
      mergeRunEvents(state.events.filter(event => event.run_id === runId));
      renderEvents();
    } catch (error) {
      if (generation !== state.generation || error.name === "AbortError") return;
      console.warn("Run activity unavailable", error);
    } finally {
      if (state.runController === controller) state.runController = null;
    }
  }

  function handleUnauthorized(generation) {
    if (generation !== state.generation) return;
    state.generation += 1;
    clearTimeout(state.pollTimer);
    state.pollController?.abort();
    state.runController?.abort();
    state.pollController = null;
    state.runController = null;
    state.stopped = true;
    state.token = "";
    state.selectedRunEvents = null;
    state.selectedRunEventsFor = null;
    $("#token").value = "";
    $("#dashboard").classList.add("hidden");
    $("#logout").classList.add("hidden");
    $("#auth-gate").classList.remove("hidden");
    showAuthError("The viewer token was rejected. Enter a valid token to reconnect.");
    setConnection("offline", "Authentication required");
    render();
  }

  function updateTopology() {
    const selected = state.runs.find(run => run.run_id === state.selectedRunId);
    const activeRuns = state.runs.filter(run => run.status === "running");
    const recentlyCreated = run => isFresh(run.created_at, 15);
    const freshWorker = run => (run.agents || []).some(agent =>
      agent.status === "running" && isFresh(agent.last_activity || run.last_activity, 120));
    const animatedRuns = activeRuns.filter(run => recentlyCreated(run) || freshWorker(run));
    const anyActive = animatedRuns.length > 0 && state.connected && !state.stale;
    for (const component of document.querySelectorAll("[data-component]")) {
      component.classList.remove("is-running", "is-completed", "is-failed", "is-timed_out");
    }
    for (const agentNode of document.querySelectorAll("[data-agent]")) {
      agentNode.classList.remove("is-running", "is-completed", "is-failed", "is-timed_out");
      agentNode.removeAttribute("title");
    }
    if (anyActive) {
      $("[data-component='orchestrator']").classList.add("is-running");
      $("[data-component='gateway']").classList.add("is-running");
      for (const run of animatedRuns) {
        for (const agent of run.agents || []) {
          const roleNode = $(`[data-agent="${CSS.escape(String(agent.role))}"]`);
          if (!roleNode) continue;
          const agentStatus = normalizedStatus(agent.status);
          if (["running", "completed", "failed", "timed_out"].includes(agentStatus)) roleNode.classList.add(`is-${agentStatus}`);
          const detail = agent.instance_id ? ` · ${agent.instance_id}` : "";
          roleNode.title = `${titleCase(agent.role)} · ${titleCase(agent.status)}${detail}`;
        }
      }
      setText("#orchestrator-label", `${animatedRuns.length} active workflow${animatedRuns.length === 1 ? "" : "s"}`);
    } else {
      setText("#orchestrator-label", "workflow graph");
    }
    const latestStatus = normalizedStatus(selected?.status);
    const ledger = $("[data-component='ledger']");
    if (state.integrity?.valid === true) ledger.classList.add("is-completed");
    else if (state.integrity?.valid === false) ledger.classList.add("is-failed");
    if (latestStatus === "failed" || latestStatus === "revoked") $("[data-component='orchestrator']").classList.add("is-failed");
    const otlp = $("[data-component='otlp']");
    if (state.telemetry?.last_error) otlp.classList.add("is-failed");
    else if (state.connected && !state.stale && state.telemetry?.enabled === true && Number(state.telemetry.pending) > 0) otlp.classList.add("is-running");
    else if (state.telemetry?.enabled === true && Number(state.telemetry.pending) === 0) otlp.classList.add("is-completed");
    document.querySelectorAll(".map-node").forEach(item => item.dataset.state = state.stale ? "stale" : state.connected ? "fresh" : "offline");
  }

  function render() {
    renderMetrics();
    renderRuns();
    renderSelectedRun();
    renderEvents();
    updateTopology();
  }

  $("#token-form").addEventListener("submit", event => {
    event.preventDefault();
    const token = $("#token").value.trim();
    if (!token) { showAuthError("Paste the viewer token to connect."); return; }
    connect(token);
  });
  $("#logout").addEventListener("click", lockViewer);
  setConnection("offline", "Disconnected");
})();
