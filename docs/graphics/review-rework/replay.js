(function (root) {
  'use strict';
  const states = ['not_arrived', 'waiting_execution', 'executing', 'awaiting_review', 'reviewing', 'accepted'];
  const labels = {
    not_arrived: 'Not yet arrived', waiting_execution: 'Waiting for execution',
    executing: 'Executing', awaiting_review: 'Waiting for review',
    reviewing: 'In review', accepted: 'Accepted',
  };
  const policyNames = { fifo: 'Arrival order (FIFO)', corrections_first: 'Corrections first' };

  function stateAt(task, tick) {
    if (tick < task.arrival_tick) return { state: 'not_arrived', attempt: 0 };
    if (task.accepted_tick !== null && tick >= task.accepted_tick) {
      return { state: 'accepted', attempt: task.attempts.length };
    }
    const attempt = task.attempts.findLast(item => item.requested_tick <= tick);
    for (const [field, state] of [
      ['review_start_tick', 'reviewing'], ['ready_tick', 'awaiting_review'],
      ['execution_start_tick', 'executing'],
    ]) {
      if (attempt[field] !== null && tick >= attempt[field]) return { state, attempt: attempt.number };
    }
    return { state: 'waiting_execution', attempt: attempt.number };
  }

  function snapshot(policy, tick) {
    const counts = Object.fromEntries(states.map(state => [state, 0]));
    policy.tasks.forEach(task => counts[stateAt(task, tick).state]++);
    counts.unfinished = policy.tasks.length - counts.not_arrived - counts.accepted;
    const saved = policy.samples.findLast(sample => sample.tick <= tick);
    if (!saved || Object.entries(counts).some(([key, value]) => value !== saved[key])) {
      throw new Error('Task states do not reconcile with the saved trace. Replay stopped.');
    }
    return counts;
  }

  function segments(task) {
    return task.attempts.flatMap(attempt => [
      ['waiting_execution', attempt.requested_tick, attempt.execution_start_tick],
      [attempt.number === 2 ? 'correcting' : 'executing', attempt.execution_start_tick, attempt.ready_tick],
      ['awaiting_review', attempt.ready_tick, attempt.review_start_tick],
      ['reviewing', attempt.review_start_tick, attempt.review_end_tick],
    ].filter(([, start, end]) => start !== null && end !== null && end > start)
      .map(([state, start, end]) => ({ state, start, end, attempt: attempt.number })));
  }

  function outcomes(data) {
    const deltas = data.comparison.tasks.map(task => task.turnaround_delta);
    return {
      earlier: deltas.filter(delta => delta < 0).length,
      later: deltas.filter(delta => delta > 0).length,
      unchanged: deltas.filter(delta => delta === 0).length,
    };
  }

  function mount() {
    const $ = id => document.getElementById(id);
    const data = JSON.parse($('rework-evidence').textContent);
    const endTick = Math.max(...data.policies.map(policy => policy.drain.tick));
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const colors = {
      waiting_execution: '#efd1a8', awaiting_review: '#efd1a8', executing: '#3179b7',
      correcting: '#8060a8', reviewing: '#21866b',
    };
    let timer = null;
    const number = value => value.toLocaleString('en-GB', { maximumFractionDigits: 2 });
    const deltaText = value => value < 0 ? `${-value} ticks earlier` : value > 0 ? `${value} ticks later` : 'Unchanged';
    const element = (tag, text) => {
      const node = document.createElement(tag);
      if (text !== undefined) node.textContent = text;
      return node;
    };
    const svgNode = (tag, attrs, text) => {
      const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
      if (text !== undefined) node.textContent = text;
      return node;
    };

    function pause() {
      clearInterval(timer);
      timer = null;
      $('rework-play').textContent = 'Play';
    }

    function drawTimeline(taskId, tick) {
      const svg = $('rework-timeline');
      svg.replaceChildren();
      const left = 175, width = 710;
      const x = value => left + value / endTick * width;
      const title = svgNode('title', {}, `Task ${taskId + 1}: the same task in both review orders`);
      svg.append(title);
      data.policies.forEach((policy, index) => {
        const task = policy.tasks[taskId], y = 33 + index * 59;
        svg.append(svgNode('text', { x: 0, y: y + 16, 'font-size': 14 }, policyNames[policy.name]));
        for (const segment of segments(task)) {
          const rect = svgNode('rect', {
            x: x(segment.start), y, width: x(segment.end) - x(segment.start), height: 23,
            fill: colors[segment.state], stroke: '#ffffff', 'stroke-width': 1,
          });
          rect.append(svgNode('title', {}, `${labels[segment.state] || 'Correction execution'}: ` +
            `${segment.start} to ${segment.end} (${segment.end - segment.start} ticks)`));
          svg.append(rect);
        }
        svg.append(svgNode('text', { x: x(task.accepted_tick), y: y - 7, 'text-anchor': 'end', 'font-size': 13 },
          `Accepted ${task.accepted_tick}`));
      });
      for (let step = 0; step <= 4; step++) {
        const time = endTick * step / 4;
        svg.append(svgNode('text', { x: x(time), y: 149, 'text-anchor': 'middle', 'font-size': 12 }, number(time)));
      }
      svg.append(svgNode('line', { x1: x(tick), x2: x(tick), y1: 17, y2: 126, stroke: '#172c3a', 'stroke-width': 2 }));
      svg.append(svgNode('text', { x: 0, y: 149, 'font-size': 13 }, 'Logical tick'));
    }

    function render() {
      try {
        const tick = Number($('rework-tick').value);
        const taskId = Number($('rework-task').value);
        $('rework-tick-value').textContent = tick;
        data.policies.forEach(policy => {
          const counts = snapshot(policy, tick);
          const card = document.querySelector(`[data-rework-policy="${policy.name}"]`);
          card.querySelectorAll('[data-count]').forEach(node => { node.textContent = counts[node.dataset.count]; });
          const current = stateAt(policy.tasks[taskId], tick);
          const suffix = current.attempt === 2 && current.state !== 'accepted' ? ' · correction pass' : '';
          card.querySelector('[data-task-state]').textContent = `Task ${taskId + 1}: ${labels[current.state]}${suffix}`;
        });
        const task = data.policies[0].tasks[taskId];
        const change = data.comparison.tasks[taskId].turnaround_delta;
        $('rework-task-summary').textContent = `Task ${taskId + 1} ${task.needs_correction ? 'requires one correction' : 'passes its first review'}. ` +
          `${deltaText(change)} with correction priority. Times below cover its full journey.`;
        $('rework-task-details').replaceChildren();
        data.policies.forEach(policy => {
          const item = policy.tasks[taskId], row = element('tr');
          [policyNames[policy.name], item.arrival_tick, item.attempts[0].review_start_tick,
            item.first_review_wait, item.accepted_tick, item.turnaround]
            .forEach(value => row.append(element('td', value)));
          $('rework-task-details').append(row);
        });
        drawTimeline(taskId, tick);
      } catch (error) {
        pause();
        $('rework-error').hidden = false;
        $('rework-error').textContent = error.message;
      }
    }

    function seek(tick) { pause(); $('rework-tick').value = tick; render(); }
    function play() {
      if (reduced.matches || !$('rework-error').hidden) return;
      if (timer) { pause(); return; }
      if (Number($('rework-tick').value) >= endTick) $('rework-tick').value = 0;
      $('rework-play').textContent = 'Pause';
      timer = setInterval(() => {
        const tick = Math.min(endTick, Number($('rework-tick').value) + 1);
        $('rework-tick').value = tick;
        render();
        if (tick === endTick) pause();
      }, 1000 / Number($('rework-speed').value));
    }
    function motion() {
      if (reduced.matches) pause();
      $('rework-play').disabled = reduced.matches;
      $('rework-motion').textContent = reduced.matches
        ? 'Reduced motion: use the slider and milestone buttons. Playback is disabled.'
        : 'Playback changes viewing speed only. These ticks are not seconds of measured work.';
    }

    const changes = outcomes(data);
    $('rework-outcomes').textContent = `${changes.earlier} tasks finish earlier · ${changes.later} later · ${changes.unchanged} unchanged`;
    const metrics = [
      ['Mean arrival to acceptance · all 24', policy => policy.metrics.turnaround.mean],
      ['Mean arrival to acceptance · six corrected', policy => policy.metrics.turnaround_by_group.corrected.mean],
      ['Mean arrival to acceptance · 18 first-pass', policy => policy.metrics.turnaround_by_group.first_pass.mean],
      ['Mean ready-to-first-review wait · all 24', policy => policy.metrics.first_review_wait.mean],
      ['Last acceptance · tick from zero', policy => policy.drain.tick],
    ];
    metrics.forEach(([label, value]) => {
      const row = element('tr');
      const heading = element('th', label); heading.scope = 'row'; row.append(heading);
      data.policies.forEach(policy => row.append(element('td', number(value(policy)))));
      $('rework-metrics').append(row);
    });
    data.comparison.tasks.forEach(change => {
      const id = change.task_id;
      const option = element('option', `Task ${id + 1}${change.needs_correction ? ' · correction' : ''} · ${deltaText(change.turnaround_delta)}`);
      option.value = id; $('rework-task').append(option);
      const row = element('tr'), cell = element('td'), button = element('button', `Task ${id + 1}`);
      button.type = 'button'; button.setAttribute('aria-label', `Inspect task ${id + 1}`);
      button.addEventListener('click', () => { pause(); $('rework-task').value = id; render(); $('rework-task').focus(); });
      cell.append(button); row.append(cell);
      [change.needs_correction ? 'One correction' : 'First-pass',
        data.policies[0].tasks[id].accepted_tick, data.policies[1].tasks[id].accepted_tick,
        deltaText(change.turnaround_delta)].forEach(value => row.append(element('td', value)));
      $('rework-all-tasks').append(row);
    });
    $('rework-task').value = 7;
    $('rework-tick').max = endTick;
    $('rework-tick').value = data.inputs.observation_horizon;
    $('rework-tick').addEventListener('input', () => { pause(); render(); });
    $('rework-task').addEventListener('change', () => { pause(); render(); });
    $('rework-play').addEventListener('click', play);
    $('rework-speed').addEventListener('change', () => { if (timer) { pause(); play(); } });
    $('rework-start').addEventListener('click', () => seek(0));
    $('rework-horizon').addEventListener('click', () => seek(data.inputs.observation_horizon));
    $('rework-tail').addEventListener('click', () => { $('rework-task').value = 23; seek(182); });
    $('rework-end').addEventListener('click', () => seek(endTick));
    document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
    reduced.addEventListener('change', motion);
    $('rework-scenario-hash').textContent = data.scenario_sha256;
    $('rework-report-hash').textContent = data.report_sha256;
    motion(); render();
  }

  const api = { stateAt, snapshot, segments, outcomes };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.ReviewReworkDemo = api; mount(); }
})(globalThis);
