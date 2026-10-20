(function (root) {
  'use strict';

  const MAX_TICK = 50000;
  const TASK_FIELDS = [
    'task_id', 'arrival_tick', 'admission_tick', 'ready_tick',
    'review_start_tick', 'decision_tick',
  ];
  const SAMPLE_FIELDS = [
    'tick', 'queued', 'executing', 'awaiting_review', 'reviewing', 'decided', 'wip',
  ];
  const STATES = [
    'not_arrived', 'queued', 'executing', 'awaiting_review', 'reviewing', 'decided',
  ];

  function object(value, label) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      throw new TypeError(`${label} must be an object`);
    }
    return value;
  }

  function integer(value, label, maximum = MAX_TICK) {
    if (!Number.isSafeInteger(value) || value < 0 || value > maximum) {
      throw new TypeError(`${label} must be a safe logical integer in [0, ${maximum}]`);
    }
    return value;
  }

  function requiredKeys(value, keys, label) {
    for (const key of keys) {
      if (!Object.prototype.hasOwnProperty.call(value, key)) {
        throw new TypeError(`${label}.${key} is required`);
      }
    }
  }

  function validateTask(task, index) {
    object(task, `task[${index}]`);
    requiredKeys(task, TASK_FIELDS, `task[${index}]`);
    integer(task.task_id, `task[${index}].task_id`, 99);
    integer(task.arrival_tick, `task[${index}].arrival_tick`, 10000);
    let previous = task.arrival_tick;
    let missing = false;
    for (const field of TASK_FIELDS.slice(2)) {
      const value = task[field];
      if (value === null) {
        missing = true;
      } else {
        if (missing) throw new TypeError(`task[${index}] has a transition after a missing timestamp`);
        integer(value, `task[${index}].${field}`);
        if (value < previous) throw new TypeError(`task[${index}] timestamps are out of order`);
        previous = value;
      }
    }
  }

  function validateSamples(samples, label) {
    if (!Array.isArray(samples) || samples.length > 10000) {
      throw new TypeError(`${label} must contain at most 10000 samples`);
    }
    let previous = -1;
    for (let index = 0; index < samples.length; index += 1) {
      const sample = object(samples[index], `${label}[${index}]`);
      requiredKeys(sample, SAMPLE_FIELDS, `${label}[${index}]`);
      integer(sample.tick, `${label}[${index}].tick`);
      if (sample.tick <= previous) throw new TypeError(`${label} ticks must increase`);
      previous = sample.tick;
      for (const field of SAMPLE_FIELDS.slice(1)) {
        integer(sample[field], `${label}[${index}].${field}`, 100);
      }
    }
  }

  function prepareReport(payload) {
    object(payload, 'payload');
    const manifest = object(payload.manifest, 'manifest');
    const scenario = object(payload.scenario, 'scenario');
    const report = object(payload.report, 'report');
    if (manifest.schema_version !== 1 || manifest.experiment_type !== 'review-capacity'
      || manifest.model_version !== 'review-capacity-v1'
      || manifest.provenance !== 'synthetic_event_time_model' || manifest.status !== 'complete'
      || typeof manifest.attempt_id !== 'string' || typeof manifest.created_at !== 'string'
      || !/^[0-9a-f]{64}$/.test(manifest.scenario_sha256)
      || !/^[0-9a-f]{64}$/.test(manifest.report_sha256)) {
      throw new TypeError('manifest provenance or structure is invalid');
    }
    if (report.model_version !== manifest.model_version
      || report.provenance !== manifest.provenance
      || !Array.isArray(report.limitations)
      || report.limitations.length > 32) {
      throw new TypeError('report provenance or structure is invalid');
    }
    const inputs = object(report.inputs, 'report.inputs');
    if (JSON.stringify(inputs) !== JSON.stringify(scenario)) {
      throw new TypeError('scenario and report inputs do not match');
    }
    const horizon = integer(inputs.observation_horizon, 'observation_horizon', 10000);
    const taskCount = integer(inputs.task_count, 'task_count', 100);
    if (taskCount < 1 || !Array.isArray(inputs.policies)
      || inputs.policies.length < 1 || inputs.policies.length > 8) {
      throw new TypeError('scenario task or policy count is invalid');
    }
    if (!Array.isArray(report.policies) || report.policies.length !== inputs.policies.length) {
      throw new TypeError('report policy count does not match scenario');
    }
    let endTick = horizon;
    const names = new Set();
    for (let index = 0; index < report.policies.length; index += 1) {
      const policy = object(report.policies[index], `policies[${index}]`);
      const config = object(inputs.policies[index], `inputs.policies[${index}]`);
      if (typeof policy.name !== 'string' || policy.name !== config.name || names.has(policy.name)) {
        throw new TypeError(`policies[${index}].name is invalid`);
      }
      names.add(policy.name);
      if (policy.execution_slots !== config.execution_slots || policy.wip_limit !== config.wip_limit) {
        throw new TypeError(`policies[${index}] configuration does not match scenario`);
      }
      if (!Array.isArray(policy.tasks) || policy.tasks.length !== taskCount || taskCount > 100) {
        throw new TypeError(`policies[${index}].tasks has an invalid size`);
      }
      const taskIds = new Set();
      for (const task of policy.tasks) {
        validateTask(task, taskIds.size);
        if (taskIds.has(task.task_id)) throw new TypeError(`policies[${index}] has duplicate task ids`);
        taskIds.add(task.task_id);
      }
      validateSamples(policy.samples, `policies[${index}].samples`);
      const horizonMetrics = object(policy.horizon, `policies[${index}].horizon`);
      integer(horizonMetrics.tick, `policies[${index}].horizon.tick`, 10000);
      for (const key of ['decided', 'pending', 'not_arrived']) {
        integer(horizonMetrics[key], `policies[${index}].horizon.${key}`, 100);
      }
      for (const key of ['queue_peaks', 'queue_means']) {
        const values = object(horizonMetrics[key], `policies[${index}].horizon.${key}`);
        for (const field of ['queued', 'awaiting_review', 'wip']) {
          const value = values[field];
          const unavailableMean = key === 'queue_means' && horizon === 0 && value === null;
          if (!unavailableMean && (!Number.isFinite(value) || value < 0)) {
            throw new TypeError(`policies[${index}].horizon.${key}.${field} is invalid`);
          }
        }
      }
      for (const key of ['latency', 'admission_wait', 'review_wait']) {
        const distribution = object(horizonMetrics[key], `policies[${index}].horizon.${key}`);
        integer(distribution.count, `policies[${index}].horizon.${key}.count`, 100);
        for (const field of ['p50', 'p95']) {
          if (distribution[field] !== null) integer(distribution[field], `${key}.${field}`);
        }
      }
      const drain = object(policy.drain, `policies[${index}].drain`);
      if (typeof drain.complete !== 'boolean') {
        throw new TypeError(`policies[${index}].drain.complete must be boolean`);
      }
      integer(drain.decided, `policies[${index}].drain.decided`, 100);
      integer(drain.pending, `policies[${index}].drain.pending`, 100);
      if (drain.makespan !== null) {
        integer(drain.makespan, `policies[${index}].drain.makespan`);
      }
      integer(drain.end_tick, `policies[${index}].drain.end_tick`);
      endTick = Math.max(endTick, drain.end_tick);
    }
    return { manifest, inputs, policies: report.policies, horizon, endTick };
  }

  function snapshot(policy, tick) {
    object(policy, 'policy');
    integer(tick, 'tick');
    if (!Array.isArray(policy.tasks) || policy.tasks.length > 100) {
      throw new TypeError('policy.tasks must contain at most 100 tasks');
    }
    const groups = Object.fromEntries(STATES.map((state) => [state, []]));
    for (let index = 0; index < policy.tasks.length; index += 1) {
      const task = policy.tasks[index];
      validateTask(task, index);
      let state;
      if (task.arrival_tick > tick) state = 'not_arrived';
      else if (task.decision_tick !== null && task.decision_tick <= tick) state = 'decided';
      else if (task.review_start_tick !== null && task.review_start_tick <= tick) state = 'reviewing';
      else if (task.ready_tick !== null && task.ready_tick <= tick) state = 'awaiting_review';
      else if (task.admission_tick !== null && task.admission_tick <= tick) state = 'executing';
      else state = 'queued';
      groups[state].push(task.task_id);
    }
    const counts = Object.fromEntries(STATES.map((state) => [state, groups[state].length]));
    counts.wip = counts.executing + counts.awaiting_review + counts.reviewing;
    counts.pending = policy.tasks.length - counts.decided;
    return { counts, groups };
  }

  function stepPoints(samples, field, endTick) {
    if (!Array.isArray(samples) || samples.length < 1 || samples.length > 10000) {
      throw new TypeError('samples must contain 1 to 10000 entries');
    }
    if (typeof field !== 'string') throw new TypeError('field must be a string');
    integer(endTick, 'endTick');
    let previousTick = -1;
    for (let index = 0; index < samples.length; index += 1) {
      const sample = object(samples[index], `samples[${index}]`);
      integer(sample.tick, `samples[${index}].tick`);
      if (sample.tick <= previousTick) throw new TypeError('sample ticks must increase');
      if (!Number.isFinite(sample[field])) {
        throw new TypeError(`samples[${index}].${field} must be finite`);
      }
      previousTick = sample.tick;
    }
    if (endTick < samples[samples.length - 1].tick) {
      throw new TypeError('endTick precedes the final sample');
    }
    const points = [[0, samples[0][field]]];
    let value = samples[0][field];
    if (!Number.isFinite(value)) throw new TypeError(`samples[0].${field} must be finite`);
    for (const sample of samples.slice(1)) {
      const next = sample[field];
      if (!Number.isFinite(next)) throw new TypeError(`sample.${field} must be finite`);
      points.push([sample.tick, value], [sample.tick, next]);
      value = next;
    }
    if (endTick > samples[samples.length - 1].tick) points.push([endTick, value]);
    return points;
  }

  root.LabReviewCapacity = { prepareReport, snapshot, stepPoints };
}(globalThis));
