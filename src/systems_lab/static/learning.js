/* Learning Dashboard - Observer Interface
 * Displays gateway flow state, telemetry, run history and events.
 * Calls checkpoint module when available.
 */
(() => {
  'use strict';

  const safeReadNumber = (value) => {
    if (typeof value !== 'number') return null;
    return Number.isFinite(value) && value >= 0 ? value : null;
  };

  const formatTimestamp = (ts) => {
    const n = safeReadNumber(ts);
    if (n === null) return 'Unknown';
    const d = new Date(n * 1000);
    return isNaN(d.getTime()) ? 'Unknown' : d.toLocaleTimeString();
  };

  const formatAge = (seconds) => {
    const s = safeReadNumber(seconds);
    if (s === null) return 'Unknown';
    if (s < 60) return `${Math.floor(s)}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    return `${Math.floor(s / 3600)}h`;
  };

  const formatDuration = (seconds) => {
    const s = safeReadNumber(seconds);
    if (s === null) return 'Unknown';
    if (s < 1) return `${Math.round(s * 1000)}ms`;
    if (s < 60) return `${s.toFixed(1)}s`;
    return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  };

  class LabLearning {
    constructor() {
      this.state = null;
      this.generation = 0;
      this.snapshots = [];
      this.lastGapGeneration = null;
    }

    render(state) {
      this.state = state;
      if (state.generation !== this.generation) {
        this.generation = state.generation;
        this.snapshots = [];
        this.lastGapGeneration = null;
      }

      this.renderFlow(state);
      this.renderHistory(state);
      this.renderControl(state);

      if (globalThis.LabCheckpoint) {
        globalThis.LabCheckpoint.render(state);
      }
    }

    reset() {
      this.state = null;
      this.generation = 0;
      this.snapshots = [];
      this.lastGapGeneration = null;

      const flow = document.getElementById('learning-flow');
      const history = document.getElementById('learning-history');
      const control = document.getElementById('learning-control');

      if (flow) flow.replaceChildren();
      if (history) history.replaceChildren();
      if (control) control.replaceChildren();

      if (globalThis.LabCheckpoint) {
        globalThis.LabCheckpoint.reset();
      }
    }

    markStale() {
      if (this.lastGapGeneration !== this.generation) {
        this.snapshots.push(null);
        this.lastGapGeneration = this.generation;
        if (this.snapshots.length > 120) {
          this.snapshots.shift();
        }
      }
      if (this.state) {
        this.renderHistory(this.state);
      }
    }

    renderFlow(state) {
      const container = document.getElementById('learning-flow');
      if (!container) return;

      const { flow, telemetry, connected, stale } = state;

      if (!flow) {
        container.replaceChildren(this.createText('Waiting for gateway data.'));
        return;
      }

      const content = document.createElement('div');

      const lanesDiv = document.createElement('div');
      lanesDiv.className = 'flow-lanes';

      const running = safeReadNumber(flow.counts?.running);
      const awaiting = safeReadNumber(flow.counts?.awaiting_review);
      const accepted = safeReadNumber(flow.counts?.accepted);
      const rejected = safeReadNumber(flow.counts?.rejected);
      const revoked = safeReadNumber(flow.counts?.revoked);
      const workflowAge = flow.oldest_workflow_age_seconds;
      const reviewAge = flow.oldest_review_age_seconds;

      lanesDiv.appendChild(this.createLane('In workflow', running, workflowAge, 'Oldest workflow'));
      lanesDiv.appendChild(this.createLane('Needs your review', awaiting, reviewAge, 'Oldest review wait'));

      const finishedCount = (accepted !== null && rejected !== null) ? accepted + rejected : null;
      const finishedLane = this.createLane('Finished', finishedCount, null, null);
      if (accepted !== null || rejected !== null) {
        const breakdown = document.createElement('div');
        breakdown.className = 'flow-breakdown';
        breakdown.textContent = `${accepted !== null ? accepted : '?'} accepted / ${rejected !== null ? rejected : '?'} rejected`;
        finishedLane.appendChild(breakdown);
      }
      lanesDiv.appendChild(finishedLane);

      lanesDiv.appendChild(this.createLane('Access revoked', revoked, null, null));

      content.appendChild(lanesDiv);

      const note = document.createElement('p');
      note.className = 'flow-note';
      note.textContent = 'In workflow is recorded state, not a worker health check.';
      content.appendChild(note);

      const deliveryLane = document.createElement('div');
      deliveryLane.className = 'delivery-lane';

      const deliveryLabel = document.createElement('span');
      deliveryLabel.className = 'flow-label';
      deliveryLabel.textContent = 'Observation delivery';
      deliveryLane.appendChild(deliveryLabel);

      let deliveryStatus = 'Unknown';
      let deliveryCount = null;
      let deliveryAge = null;

      if (telemetry) {
        if (telemetry.enabled === false) {
          deliveryStatus = 'Disabled';
          deliveryCount = safeReadNumber(telemetry.pending);
          deliveryAge = telemetry.oldest_pending_age_seconds;
        } else if (telemetry.enabled === true) {
          const pending = safeReadNumber(telemetry.pending);
          if (telemetry.last_error) {
            deliveryStatus = 'Delivery error';
            deliveryCount = pending;
            deliveryAge = telemetry.oldest_pending_age_seconds;
          } else if (pending !== null) {
            deliveryStatus = pending > 0 ? 'Pending' : 'Clear';
            deliveryCount = pending;
            deliveryAge = telemetry.oldest_pending_age_seconds;
          }
        }
      }

      const statusSpan = document.createElement('span');
      statusSpan.className = 'delivery-status';
      statusSpan.textContent = deliveryStatus;
      deliveryLane.appendChild(statusSpan);

      if (deliveryCount !== null) {
        const countSpan = document.createElement('strong');
        countSpan.className = 'flow-count';
        countSpan.textContent = `${deliveryCount} events pending`;
        deliveryLane.appendChild(countSpan);

        const age = safeReadNumber(deliveryAge);
        const ageSpan = document.createElement('span');
        ageSpan.className = 'flow-age';
        ageSpan.textContent = `Oldest undelivered event: ${age !== null ? formatAge(age) : 'Unknown'}`;
        deliveryLane.appendChild(ageSpan);
      }

      content.appendChild(deliveryLane);

      const deliveryNote = document.createElement('p');
      deliveryNote.className = 'flow-note';
      deliveryNote.textContent = 'Tasks and undelivered observations are counted separately.';
      content.appendChild(deliveryNote);

      if (stale) {
        const staleNotice = document.createElement('p');
        staleNotice.className = 'stale-notice';
        staleNotice.textContent = 'Last received snapshot — connection interrupted.';
        content.appendChild(staleNotice);
      }

      container.replaceChildren(content);
    }

    createLane(label, count, ageSeconds, ageLabel) {
      const lane = document.createElement('div');
      lane.className = 'flow-lane';

      const labelSpan = document.createElement('span');
      labelSpan.className = 'flow-label';
      labelSpan.textContent = label;
      lane.appendChild(labelSpan);

      const countSpan = document.createElement('strong');
      countSpan.className = 'flow-count';
      countSpan.textContent = count !== null ? String(count) : 'Unknown';
      lane.appendChild(countSpan);

      if (ageLabel !== null && ageLabel !== undefined) {
        const age = safeReadNumber(ageSeconds);
        const ageText = age !== null ? formatAge(age) : (count !== null && count > 0 ? 'Unknown' : null);

        if (ageText !== null) {
          const ageSpan = document.createElement('span');
          ageSpan.className = 'flow-age';
          ageSpan.textContent = `${ageLabel}: ${ageText}`;
          lane.appendChild(ageSpan);
        }
      }

      return lane;
    }

    renderHistory(state) {
      const container = document.getElementById('learning-history');
      if (!container) return;

      const { flow, telemetry, connected, stale } = state;

      if (connected && !stale && flow && flow.observed_at !== undefined) {
        const observed = safeReadNumber(flow.observed_at);
        if (observed !== null) {
          const existing = this.snapshots.find(s => s && s.timestamp === observed);
          if (!existing) {
            this.lastGapGeneration = null;
            const snapshot = {
              timestamp: observed,
              running: safeReadNumber(flow.counts?.running),
              awaiting_review: safeReadNumber(flow.counts?.awaiting_review),
              pending: telemetry ? safeReadNumber(telemetry.pending) : null
            };
            this.snapshots.push(snapshot);
            if (this.snapshots.length > 120) {
              this.snapshots.shift();
            }
          }
        }
      }

      const content = document.createElement('div');

      const validSnapshots = this.snapshots.filter(s => s !== null);

      if (validSnapshots.length === 0) {
        content.appendChild(this.createText('Waiting for gateway data.'));
        container.replaceChildren(content);
        return;
      }

      if (validSnapshots.length === 1) {
        const single = validSnapshots[0];
        const p = document.createElement('p');
        p.textContent = 'Waiting for a second reading.';
        content.appendChild(p);

        const counts = document.createElement('p');
        counts.textContent = `Running: ${single.running !== null ? single.running : 'Unknown'}, Awaiting review: ${single.awaiting_review !== null ? single.awaiting_review : 'Unknown'}, Pending: ${single.pending !== null ? single.pending : 'Unknown'}`;
        content.appendChild(counts);

        container.replaceChildren(content);
        return;
      }

      const chartsDiv = document.createElement('div');
      chartsDiv.className = 'history-charts';

      chartsDiv.appendChild(this.createTaskChart(this.snapshots));
      chartsDiv.appendChild(this.createDeliveryChart(this.snapshots));

      content.appendChild(chartsDiv);

      const caption = document.createElement('p');
      caption.className = 'history-caption';
      caption.textContent = 'Recent readings from this connection. This chart is not the full history.';
      content.appendChild(caption);

      if (state.events && state.events.length > 0) {
        const sessionStart = validSnapshots.length > 0 ? validSnapshots[0].timestamp : 0;
        const sessionEnd = validSnapshots.length > 0 ? validSnapshots.at(-1).timestamp : Infinity;

        const allowedActions = new Set([
          'run.ready',
          'run.decision',
          'run.revoke',
          'worker.failed',
          'worker.timed_out'
        ]);

        const actionLabels = {
          'run.ready': 'Ready',
          'run.decision': 'Decision',
          'run.revoke': 'Revoked',
          'worker.failed': 'Failed',
          'worker.timed_out': 'Timed out'
        };

        const relevantEvents = state.events
          .filter(e => {
            const ts = safeReadNumber(e.timestamp);
            return ts !== null && ts >= sessionStart && ts <= sessionEnd && allowedActions.has(e.action);
          })
          .slice(-5);

        if (relevantEvents.length > 0) {
          const markersDiv = document.createElement('div');
          markersDiv.className = 'history-markers';

          const heading = document.createElement('h4');
          heading.textContent = 'Recent events';
          markersDiv.appendChild(heading);

          const list = document.createElement('ul');
          relevantEvents.forEach(e => {
            const item = document.createElement('li');
            const label = actionLabels[e.action] || e.action;
            item.textContent = `${formatTimestamp(e.timestamp)}: ${label}`;
            list.appendChild(item);
          });
          markersDiv.appendChild(list);

          content.appendChild(markersDiv);
        }
      }

      container.replaceChildren(content);
    }

    createTaskChart(snapshots) {
      const validSnapshots = snapshots.filter(s => s !== null);
      const runningData = validSnapshots.map(s => ({ t: s.timestamp, v: s.running }));
      const awaitingData = validSnapshots.map(s => ({ t: s.timestamp, v: s.awaiting_review }));

      const maxRunning = Math.max(...runningData.map(d => d.v !== null ? d.v : 0), 1);
      const maxAwaiting = Math.max(...awaitingData.map(d => d.v !== null ? d.v : 0), 1);
      const maxY = Math.max(maxRunning, maxAwaiting, 1);

      const h3 = document.createElement('h3');
      h3.className = 'history-chart-title';
      h3.textContent = 'Tasks in workflow';

      const svg = this.createSVGChart('Tasks in workflow', 'Running and awaiting review over time');
      const runningPath = this.createPath(snapshots, runningData, maxY);
      runningPath.setAttribute('class', 'chart-line-running');
      svg.appendChild(runningPath);

      const awaitingPath = this.createPath(snapshots, awaitingData, maxY);
      awaitingPath.setAttribute('class', 'chart-line-awaiting');
      awaitingPath.setAttribute('stroke-dasharray', '6 4');
      svg.appendChild(awaitingPath);

      this.addAxes(svg, validSnapshots, maxY);

      const legend = document.createElement('div');
      legend.className = 'chart-legend';

      const runningItem = document.createElement('span');
      runningItem.className = 'legend-item';
      const runningColor = document.createElement('span');
      runningColor.className = 'legend-color legend-running';
      runningItem.appendChild(runningColor);
      runningItem.appendChild(document.createTextNode('In workflow'));
      legend.appendChild(runningItem);

      const awaitingItem = document.createElement('span');
      awaitingItem.className = 'legend-item';
      const awaitingColor = document.createElement('span');
      awaitingColor.className = 'legend-color legend-awaiting';
      awaitingItem.appendChild(awaitingColor);
      awaitingItem.appendChild(document.createTextNode('Needs your review'));
      legend.appendChild(awaitingItem);

      const wrapper = document.createElement('div');
      wrapper.className = 'history-chart';
      wrapper.appendChild(h3);
      wrapper.appendChild(svg);
      wrapper.appendChild(legend);

      return wrapper;
    }

    createDeliveryChart(snapshots) {
      const validSnapshots = snapshots.filter(s => s !== null);
      const pendingData = validSnapshots.map(s => ({ t: s.timestamp, v: s.pending }));

      const maxPending = Math.max(...pendingData.map(d => d.v !== null ? d.v : 0), 1);

      const h3 = document.createElement('h3');
      h3.className = 'history-chart-title';
      h3.textContent = 'Observations awaiting delivery';

      const svg = this.createSVGChart('Delivery queue', 'Pending observations over time');
      const pendingPath = this.createPath(snapshots, pendingData, maxPending);
      pendingPath.setAttribute('class', 'chart-line-pending');
      svg.appendChild(pendingPath);

      this.addAxes(svg, validSnapshots, maxPending);

      const legend = document.createElement('div');
      legend.className = 'chart-legend';

      const pendingItem = document.createElement('span');
      pendingItem.className = 'legend-item';
      const pendingColor = document.createElement('span');
      pendingColor.className = 'legend-color legend-pending';
      pendingItem.appendChild(pendingColor);
      pendingItem.appendChild(document.createTextNode('Events pending'));
      legend.appendChild(pendingItem);

      const wrapper = document.createElement('div');
      wrapper.className = 'history-chart';
      wrapper.appendChild(h3);
      wrapper.appendChild(svg);
      wrapper.appendChild(legend);

      return wrapper;
    }

    createSVGChart(title, desc) {
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 420 160');
      svg.setAttribute('width', '100%');
      svg.setAttribute('role', 'img');

      const titleEl = document.createElementNS('http://www.w3.org/2000/svg', 'title');
      titleEl.textContent = title;
      svg.appendChild(titleEl);

      const descEl = document.createElementNS('http://www.w3.org/2000/svg', 'desc');
      descEl.textContent = desc;
      svg.appendChild(descEl);

      return svg;
    }

    createPath(allSnapshots, data, maxY) {
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const parts = [];
      let currentSegment = [];

      allSnapshots.forEach((snapshot, i) => {
        if (snapshot === null) {
          if (currentSegment.length > 0) {
            parts.push(currentSegment);
            currentSegment = [];
          }
        } else {
          const point = data.find(d => d.t === snapshot.timestamp);
          if (point && point.v !== null) {
            currentSegment.push(point);
          } else {
            if (currentSegment.length > 0) {
              parts.push(currentSegment);
              currentSegment = [];
            }
          }
        }
      });

      if (currentSegment.length > 0) {
        parts.push(currentSegment);
      }

      const allTimestamps = allSnapshots.filter(s => s !== null).map(s => s.timestamp);
      if (allTimestamps.length === 0) {
        path.setAttribute('d', '');
        return path;
      }

      const minT = allTimestamps[0];
      const maxT = allTimestamps[allTimestamps.length - 1];
      const rangeT = maxT - minT || 1;

      const pathData = parts.map(segment => {
        return segment.map((point, i) => {
          const x = 40 + ((point.t - minT) / rangeT) * 360;
          const y = 140 - ((point.v / maxY) * 120);
          return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
        }).join(' ');
      }).join(' ');

      path.setAttribute('d', pathData);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke-width', '2');

      return path;
    }

    addAxes(svg, validSnapshots, maxY) {
      const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      yAxis.setAttribute('x', '5');
      yAxis.setAttribute('y', '20');
      yAxis.setAttribute('class', 'axis-label');
      yAxis.textContent = String(Math.ceil(maxY));
      svg.appendChild(yAxis);

      const yZero = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      yZero.setAttribute('x', '5');
      yZero.setAttribute('y', '155');
      yZero.setAttribute('class', 'axis-label');
      yZero.textContent = '0';
      svg.appendChild(yZero);

      if (validSnapshots.length > 0) {
        const startTime = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        startTime.setAttribute('x', '40');
        startTime.setAttribute('y', '155');
        startTime.setAttribute('class', 'axis-label');
        startTime.textContent = formatTimestamp(validSnapshots[0].timestamp);
        svg.appendChild(startTime);

        const endTime = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        endTime.setAttribute('x', '350');
        endTime.setAttribute('y', '155');
        endTime.setAttribute('class', 'axis-label');
        endTime.textContent = formatTimestamp(validSnapshots[validSnapshots.length - 1].timestamp);
        svg.appendChild(endTime);
      }
    }

    renderControl(state) {
      const container = document.getElementById('learning-control');
      if (!container) return;

      const { selectedRunId, runs } = state;

      const content = document.createElement('div');

      if (!selectedRunId) {
        content.appendChild(this.createText('Select a run to view details.'));
        container.replaceChildren(content);
        return;
      }

      const run = runs?.find(r => r.run_id === selectedRunId);

      if (!run) {
        content.appendChild(this.createText('Selected run not found.'));
        container.replaceChildren(content);
        return;
      }

      const fixtureNote = document.createElement('p');
      fixtureNote.className = 'fixture-note';
      const modelMode = run.model_mode;
      if (modelMode === 'fixture') {
        fixtureNote.textContent = 'Fixture model results illustrate the workflow; they do not establish real model quality.';
      } else if (modelMode === 'live') {
        fixtureNote.textContent = 'Live model run. Outputs still need review.';
      } else {
        fixtureNote.textContent = 'Model mode unknown.';
      }
      content.appendChild(fixtureNote);

      const heading = document.createElement('h3');
      heading.textContent = `Run details`;
      content.appendChild(heading);

      const statusP = document.createElement('p');
      statusP.textContent = `Status: ${run.status}, Stage: ${run.stage || 'Unknown'}, Mode: ${run.model_mode || 'Unknown'}`;
      content.appendChild(statusP);

      const nextStep = this.getNextStep(run.status);
      const nextStepP = document.createElement('p');
      nextStepP.className = 'next-step';
      nextStepP.textContent = nextStep;
      content.appendChild(nextStepP);

      const commandsNote = document.createElement('p');
      commandsNote.className = 'control-note';
      commandsNote.textContent = 'These commands require the operator terminal. This viewer cannot change a run.';
      content.appendChild(commandsNote);

      const statusCmd = this.createCommandBlock(
        'Check run status',
        `uv run systems-lab --gateway ${location.origin} status ${run.run_id}`
      );
      content.appendChild(statusCmd);

      if (run.status === 'running' || run.status === 'awaiting_review') {
        const revokeCmd = this.createCommandBlock(
          'Revoke access',
          `uv run systems-lab --gateway ${location.origin} revoke ${run.run_id}`
        );
        content.appendChild(revokeCmd);

        const dockerNote = document.createElement('p');
        dockerNote.className = 'control-note';
        dockerNote.textContent = 'Use --stop-containers to stop Docker containers (Docker environments only).';
        content.appendChild(dockerNote);
      }

      if (run.agents && run.agents.length > 0) {
        const agentsDiv = document.createElement('div');
        agentsDiv.className = 'agent-evidence';

        const agentsHeading = document.createElement('h4');
        agentsHeading.textContent = 'Agents';
        agentsDiv.appendChild(agentsHeading);

        run.agents.forEach(agent => {
          const agentDiv = document.createElement('div');
          agentDiv.className = 'agent-item';

          const roleLine = document.createElement('p');
          const roleStrong = document.createElement('strong');
          roleStrong.textContent = agent.role || 'Unknown role';
          roleLine.appendChild(roleStrong);
          roleLine.appendChild(document.createTextNode(`: ${agent.status || 'Unknown'}`));
          agentDiv.appendChild(roleLine);

          if (agent.instance_id) {
            const instanceP = document.createElement('p');
            instanceP.textContent = `Instance: ${agent.instance_id}`;
            agentDiv.appendChild(instanceP);
          }

          if (agent.started_at) {
            const startedP = document.createElement('p');
            startedP.textContent = `Started: ${formatTimestamp(agent.started_at)}`;
            agentDiv.appendChild(startedP);
          }

          if (agent.completed_at) {
            const completedP = document.createElement('p');
            completedP.textContent = `Completed: ${formatTimestamp(agent.completed_at)}`;
            agentDiv.appendChild(completedP);
          }

          if (agent.duration_seconds !== undefined) {
            const duration = safeReadNumber(agent.duration_seconds);
            if (duration !== null) {
              const durationP = document.createElement('p');
              durationP.textContent = `Duration: ${formatDuration(duration)}`;
              agentDiv.appendChild(durationP);
            }
          }

          if (agent.allowed_actions && agent.allowed_actions.length > 0) {
            const toolsP = document.createElement('p');
            toolsP.textContent = `Tools for this role: ${agent.allowed_actions.join(', ')}`;
            agentDiv.appendChild(toolsP);
          }

          agentsDiv.appendChild(agentDiv);
        });

        const grantNote = document.createElement('p');
        grantNote.className = 'control-note';
        grantNote.textContent = 'Tools listed here are the role limits. The gateway checks access for every call.';
        content.appendChild(grantNote);

        content.appendChild(agentsDiv);
      }

      container.replaceChildren(content);
    }

    getNextStep(status) {
      switch (status) {
        case 'running':
          return 'Observe recorded progress or revoke access via operator terminal.';
        case 'awaiting_review':
          return 'Inspect artifacts then approve or reject with current digest in operator terminal.';
        case 'revoked':
          return 'Access revoked. Stopping process is separate.';
        case 'accepted':
          return 'Run accepted. Review is complete.';
        case 'rejected':
          return 'Run rejected. Review is complete.';
        default:
          return 'Status unknown. Check operator terminal for details.';
      }
    }

    createCommandBlock(label, command) {
      const block = document.createElement('div');
      block.className = 'command-block';

      const labelP = document.createElement('p');
      labelP.textContent = label;
      block.appendChild(labelP);

      const code = document.createElement('code');
      code.textContent = command;
      code.className = 'selectable-command';
      block.appendChild(code);

      const copyBtn = document.createElement('button');
      copyBtn.textContent = 'Copy';
      copyBtn.className = 'button button-quiet';
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(command).catch(() => {
          const msg = document.createElement('span');
          msg.textContent = ' Clipboard unavailable';
          msg.className = 'copy-message';
          block.appendChild(msg);
          setTimeout(() => msg.remove(), 2000);
        });
      });
      block.appendChild(copyBtn);

      return block;
    }

    createText(text) {
      const p = document.createElement('p');
      p.textContent = text;
      return p;
    }
  }

  const instance = new LabLearning();
  globalThis.LabLearning = {
    render: (state) => instance.render(state),
    reset: () => instance.reset(),
    markStale: () => instance.markStale()
  };
})();
