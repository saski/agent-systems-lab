(() => {
  "use strict";

  const API = "/api/experiments/review-capacity";
  const COLORS = ["#9a8cf4", "#76b8f2", "#5bd2a1", "#e8b86d", "#f07a83", "#d7b3ed", "#9dd7d4", "#e6d5a0"];
  const $ = selector => document.querySelector(selector);
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const state = { token: "", generation: 0, active: false, loaded: false, attempts: [],
    attemptId: "", report: null, policy: 0, tick: 0, position: 0, playing: false,
    frame: null, lastTime: null, listController: null, reportController: null,
    cache: new Map(), reject: null, retry: null };

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = String(text);
    return item;
  }

  const number = value => value === null || value === undefined ? "—" : String(value);
  const percentiles = value => `${number(value.p50)} / ${number(value.p95)}`;

  function status(kind, message, retry = null) {
    $(".experiment-feedback").dataset.state = kind;
    $("#experiment-status").textContent = message;
    $("#experiment-empty").classList.toggle("hidden", kind !== "empty");
    $("#experiment-retry").classList.toggle("hidden", !retry);
    $("#experiment-report").classList.toggle("hidden", kind !== "ready");
    state.retry = retry;
  }

  function pause() {
    if (state.frame !== null) cancelAnimationFrame(state.frame);
    state.frame = null;
    state.lastTime = null;
    state.playing = false;
    $("#replay-play").textContent = "Play";
  }

  function setView(experiments) {
    state.active = experiments;
    if (!experiments) pause();
    $("#activity-view").classList.toggle("hidden", experiments);
    $("#experiments-view").classList.toggle("hidden", !experiments);
    for (const [id, selected] of [["#activity-nav", !experiments], ["#experiments-nav", experiments]]) {
      $(id).classList.toggle("active", selected);
      $(id).setAttribute("aria-pressed", String(selected));
    }
    $("#view-context").textContent = experiments ? "Read only · saved reports" : "Read only · live feed";
    document.title = experiments ? "Systems Lab · Experiments" : "Systems Lab · Activity";
  }

  function reset() {
    state.generation += 1;
    state.listController?.abort();
    state.reportController?.abort();
    state.listController = null;
    state.reportController = null;
    state.token = "";
    state.reject = null;
    state.report = null;
    state.attemptId = "";
    state.attempts = [];
    state.cache.clear();
    state.loaded = false;
    state.policy = 0;
    state.tick = 0;
    setView(false);
    for (const id of ["#experiment-attempt", "#replay-policy", "#comparison-rows", "#decision-chart", "#queue-chart", "#experiment-evidence"]) $(id).replaceChildren();
    $("#experiment-attempt").disabled = true;
    $("#experiment-refresh").disabled = true;
    status("idle", "Open Experiments to load saved reports.");
  }

  function connect(token, reject) {
    reset();
    state.token = token;
    state.reject = reject;
    $("#experiment-refresh").disabled = false;
  }

  async function request(path, controller, generation) {
    const response = await fetch(path, { method: "GET", cache: "no-store",
      headers: { Authorization: `Bearer ${state.token}`, Accept: "application/json" },
      signal: controller.signal });
    if (generation !== state.generation || controller.signal.aborted) throw new DOMException("Cancelled", "AbortError");
    if (response.status === 401) {
      state.reject?.();
      throw new DOMException("Authentication required", "AbortError");
    }
    if (!response.ok) {
      const error = new Error("Report request failed");
      error.status = response.status;
      throw error;
    }
    return response.json();
  }

  function errorMessage(error) {
    if (error.status === 404) return "This report is no longer available. Refresh reports to select another.";
    if (error.status === 422) return "This report is incomplete or failed validation. Refresh reports to select another.";
    if (error.status === 503) return "Report storage is unavailable. Retry when the gateway can read it.";
    return "The comparison could not be loaded. Check the gateway connection and retry.";
  }

  async function loadAttempts() {
    if (!state.token) return;
    pause();
    const generation = state.generation;
    state.listController?.abort();
    state.reportController?.abort();
    const controller = new AbortController();
    state.listController = controller;
    state.cache.clear();
    state.report = null;
    $("#experiment-attempt").disabled = true;
    status("loading", "Loading saved comparisons…");
    try {
      const payload = await request(API, controller, generation);
      if (generation !== state.generation || controller !== state.listController) return;
      if (!Array.isArray(payload.attempts) || payload.attempts.length > 50 || payload.attempts.some(item =>
        !item || typeof item.attempt_id !== "string" || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(item.attempt_id) ||
        item.status !== "complete" || item.provenance !== "synthetic_event_time_model" || typeof item.created_at !== "string")) {
        throw new Error("Invalid report listing");
      }
      state.attempts = payload.attempts.slice().sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
      state.loaded = true;
      const options = state.attempts.map(item => {
        const option = node("option", "", `${item.created_at.replace("T", " ").slice(0, 19)} UTC · ${item.attempt_id}`);
        option.value = item.attempt_id;
        return option;
      });
      $("#experiment-attempt").replaceChildren(...options);
      if (!options.length) {
        state.attemptId = "";
        status("empty", "No saved comparisons found.");
        return;
      }
      $("#experiment-attempt").disabled = false;
      const selected = state.attempts.some(item => item.attempt_id === state.attemptId)
        ? state.attemptId : state.attempts[0].attempt_id;
      $("#experiment-attempt").value = selected;
      loadReport(selected);
    } catch (error) {
      if (generation !== state.generation || controller !== state.listController || error.name === "AbortError") return;
      state.loaded = false;
      status("error", errorMessage(error), loadAttempts);
    }
  }

  async function loadReport(attemptId, force = false) {
    if (!state.token || !attemptId) return;
    pause();
    state.reportController?.abort();
    const controller = new AbortController();
    state.reportController = controller;
    const generation = state.generation;
    state.attemptId = attemptId;
    state.report = null;
    status("loading", "Loading and checking the saved comparison…");
    try {
      let report = !force && state.cache.get(attemptId);
      if (!report) {
        const payload = await request(`${API}/${encodeURIComponent(attemptId)}`, controller, generation);
        if (generation !== state.generation || controller !== state.reportController) return;
        report = globalThis.LabReviewCapacity.prepareReport(payload);
        if (report.manifest.attempt_id !== attemptId) throw new Error("Report identity mismatch");
        state.cache.set(attemptId, report);
      }
      state.report = report;
      state.policy = 0;
      state.tick = report.horizon;
      state.position = state.tick;
      renderReport();
      status("ready", `Saved comparison loaded. Observation horizon: logical tick ${report.horizon}.`);
    } catch (error) {
      if (generation !== state.generation || controller !== state.reportController || error.name === "AbortError") return;
      status("error", errorMessage(error), () => loadReport(attemptId, true));
    }
  }

  function swatch(color, label) {
    const item = node("span", "", label);
    const marker = node("i", "policy-swatch");
    marker.style.setProperty("--policy-color", color);
    marker.setAttribute("aria-hidden", "true");
    item.prepend(marker);
    return item;
  }

  function renderReport() {
    const view = state.report;
    $("#experiment-boundary").textContent = `${view.inputs.task_count} scheduled tasks · ${view.inputs.execution_ticks} execution ticks per task · ${view.inputs.review_ticks} review ticks · one synthetic reviewer.`;
    $("#comparison-caption").textContent = `Post-transition counts at logical tick ${view.horizon}; latency and waits are in logical ticks.`;
    $("#comparison-rows").replaceChildren(...view.policies.map((policy, index) => {
      const row = node("tr");
      const label = node("td");
      label.append(swatch(COLORS[index], policy.name), node("small", "", `${policy.execution_slots} execution slot${policy.execution_slots === 1 ? "" : "s"}; WIP ${policy.wip_limit === null ? "uncapped" : policy.wip_limit}`));
      const counts = globalThis.LabReviewCapacity.snapshot(policy, view.horizon).counts;
      row.append(label, ...[policy.horizon.decided, policy.horizon.pending, counts.queued, counts.awaiting_review,
        `${percentiles(policy.horizon.latency)} (n=${policy.horizon.latency.count})`,
        policy.drain.complete ? `${policy.drain.makespan} ticks; all decided` : `Incomplete; ${policy.drain.pending} pending`]
        .map(value => node("td", "", value)));
      return row;
    }));
    $("#replay-policy").replaceChildren(...view.policies.map((policy, index) => {
      const option = node("option", "", policy.name);
      option.value = String(index);
      return option;
    }));
    $("#replay-seek").max = String(view.endTick);
    const evidence = [
      ["Attempt", view.manifest.attempt_id], ["Created (UTC)", view.manifest.created_at],
      ["Model", view.manifest.model_version], ["Source", "synthetic_event_time_model"],
      ["Scenario SHA-256", view.manifest.scenario_sha256], ["Report SHA-256", view.manifest.report_sha256]
    ];
    $("#experiment-evidence").replaceChildren(...evidence.flatMap(([key, value]) => [node("dt", "", key), node("dd", "", value)]));
    renderPolicy();
    renderMotion();
  }

  function svgNode(tag, attributes, text) {
    const item = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attributes)) item.setAttribute(key, String(value));
    if (text !== undefined) item.textContent = String(text);
    return item;
  }

  function chart(host, title, lines) {
    const view = state.report;
    const width = 600, height = 220, left = 40, right = 18, top = 20, bottom = 42;
    const end = Math.max(1, view.endTick);
    const max = Math.max(1, ...lines.flatMap(line => line.points.map(point => point[1])));
    const x = tick => left + tick / end * (width - left - right);
    const y = count => height - bottom - count / max * (height - top - bottom);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, class: "experiment-chart", role: "img", "aria-label": title });
    svg.append(svgNode("title", {}, title));
    for (const count of [0, max]) {
      svg.append(svgNode("line", { x1: left, x2: width - right, y1: y(count), y2: y(count), class: "grid" }));
      svg.append(svgNode("text", { x: left - 8, y: y(count) + 4, "text-anchor": "end" }, count));
    }
    svg.append(svgNode("text", { x: left, y: height - 20 }, "0"),
      svgNode("text", { x: width - right, y: height - 20, "text-anchor": "end" }, view.endTick),
      svgNode("text", { x: width / 2, y: height - 2, "text-anchor": "middle" }, "Logical ticks"));
    for (const line of lines) svg.append(svgNode("polyline", {
      points: line.points.map(([tick, value]) => `${x(tick)},${y(value)}`).join(" "),
      fill: "none", stroke: line.color, "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-dasharray": line.dashed ? "6 4" : "none"
    }));
    svg.append(svgNode("line", { x1: x(view.horizon), x2: x(view.horizon), y1: top, y2: height - bottom, class: "horizon" }),
      svgNode("text", { x: Math.min(width - 95, x(view.horizon) + 5), y: top - 5 }, `Horizon ${view.horizon}`),
      svgNode("line", { x1: x(state.tick), x2: x(state.tick), y1: top, y2: height - bottom, class: "cursor", "data-replay-cursor": "", "data-end": end }));
    $(host).replaceChildren(svg);
  }

  function renderPolicy() {
    const view = state.report;
    const selected = view.policies[state.policy];
    $("#replay-policy-facts").textContent = `${selected.execution_slots} execution slot${selected.execution_slots === 1 ? "" : "s"} · admitted WIP ${selected.wip_limit === null ? "uncapped" : `limited to ${selected.wip_limit}`} · admission wait p50 / p95: ${percentiles(selected.horizon.admission_wait)} · review wait p50 / p95: ${percentiles(selected.horizon.review_wait)} (n=${selected.horizon.latency.count} decided at the horizon).`;
    const decisions = view.policies.map((policy, index) => ({ color: COLORS[index], dashed: index === 2, points: globalThis.LabReviewCapacity.stepPoints(policy.samples, "decided", view.endTick) }));
    chart("#decision-chart", "Cumulative simulated decisions for all policies", decisions);
    $("#decision-legend").replaceChildren(...view.policies.map((policy, index) => swatch(COLORS[index], `${policy.name}${index === 2 ? " (dashed)" : ""}`)));
    const queues = [{ name: "1 · Admission queue", field: "queued", color: "#76b8f2" }, { name: "2 · Review queue", field: "awaiting_review", color: "#e8b86d" }];
    chart("#queue-chart", `Waiting tasks for policy ${selected.name}`, queues.map(queue => ({ color: queue.color, points: globalThis.LabReviewCapacity.stepPoints(selected.samples, queue.field, view.endTick) })));
    $("#queue-legend").replaceChildren(...queues.map(queue => swatch(queue.color, queue.name)));
    $("#replay-drain").textContent = selected.drain.complete
      ? `Policy ${selected.name}: all ${view.inputs.task_count} tasks decided by logical tick ${selected.drain.end_tick}. Makespan: ${selected.drain.makespan} ticks.`
      : `Drain bound reached at tick ${selected.drain.end_tick}: ${selected.drain.pending} tasks remain unfinished. Makespan is unavailable; the replay stops at the recorded bound.`;
    renderTick();
  }

  function renderTick() {
    if (!state.report) return;
    const view = state.report;
    const snapshot = globalThis.LabReviewCapacity.snapshot(view.policies[state.policy], state.tick);
    $("#replay-seek").value = String(state.tick);
    $("#replay-seek").setAttribute("aria-valuetext", `Logical tick ${state.tick} of ${view.endTick}`);
    $("#replay-tick").textContent = `${state.tick} / ${view.endTick}`;
    $("#replay-future").textContent = `${snapshot.counts.not_arrived} not yet arrived`;
    $("#replay-totals").textContent = `${snapshot.counts.decided} decided · ${snapshot.counts.pending} unfinished · ${snapshot.counts.wip} admitted WIP`;
    for (const field of ["queued", "executing", "awaiting_review", "reviewing", "decided"]) {
      $(`[data-count="${field}"]`).textContent = String(snapshot.counts[field]);
      $(`[data-tasks="${field}"]`).replaceChildren(...snapshot.groups[field].map(id => {
        const item = node("span", "task-chip", `#${id}`);
        item.title = `Task ${id} · ${field.replaceAll("_", " ")} at logical tick ${state.tick}`;
        return item;
      }));
    }
    for (const cursor of document.querySelectorAll("[data-replay-cursor]")) {
      const x = 40 + state.tick / Number(cursor.dataset.end) * 542;
      cursor.setAttribute("x1", String(x));
      cursor.setAttribute("x2", String(x));
    }
  }

  function seek(tick) {
    if (!state.report) return;
    pause();
    state.tick = Math.max(0, Math.min(state.report.endTick, Math.floor(tick)));
    state.position = state.tick;
    renderTick();
  }

  function renderMotion() {
    $("#replay-play").disabled = motion.matches || !state.report || state.report.endTick === 0;
    $("#replay-speed").disabled = motion.matches;
    $("#replay-motion").textContent = motion.matches
      ? "Reduced motion is on. Use the tick slider or jump controls; automatic playback is disabled."
      : "Speed changes viewing time only. Seek or jump to inspect an exact logical tick.";
  }

  function frame(time) {
    if (!state.playing || !state.report || !state.active || motion.matches || document.hidden) { pause(); return; }
    const elapsed = state.lastTime === null ? 0 : Math.min(250, time - state.lastTime);
    state.lastTime = time;
    state.position = Math.min(state.report.endTick, state.position + elapsed / 1000 * 8 * Number($("#replay-speed").value));
    const tick = Math.floor(state.position);
    if (tick !== state.tick) { state.tick = tick; renderTick(); }
    if (state.position >= state.report.endTick) { pause(); return; }
    state.frame = requestAnimationFrame(frame);
  }

  $("#activity-nav").addEventListener("click", () => setView(false));
  $("#experiments-nav").addEventListener("click", () => {
    if (!state.token) return;
    setView(true);
    if (!state.loaded) loadAttempts();
  });
  $("#experiment-refresh").addEventListener("click", loadAttempts);
  $("#experiment-retry").addEventListener("click", () => state.retry?.());
  $("#experiment-attempt").addEventListener("change", event => loadReport(event.target.value));
  $("#replay-policy").addEventListener("change", event => { pause(); state.policy = Number(event.target.value); renderPolicy(); });
  $("#replay-seek").addEventListener("input", event => seek(Number(event.target.value)));
  $("#replay-start").addEventListener("click", () => seek(0));
  $("#replay-horizon").addEventListener("click", () => seek(state.report?.horizon || 0));
  $("#replay-end").addEventListener("click", () => seek(state.report?.endTick || 0));
  $("#replay-play").addEventListener("click", () => {
    if (state.playing) { pause(); return; }
    if (!state.report || motion.matches || state.report.endTick === 0) return;
    if (state.tick >= state.report.endTick) seek(0);
    state.playing = true;
    state.lastTime = null;
    $("#replay-play").textContent = "Pause";
    state.frame = requestAnimationFrame(frame);
  });
  motion.addEventListener("change", () => { pause(); renderMotion(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) pause(); });
  globalThis.LabExperiments = { connect, reset };
  reset();
})();
