const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(
  path.join(__dirname, '../../src/systems_lab/static/review-capacity.js'),
  'utf8',
);
vm.runInThisContext(source, { filename: 'review-capacity.js' });
const projection = globalThis.LabReviewCapacity;
const attempt = JSON.parse(fs.readFileSync(process.env.REVIEW_CAPACITY_TEST_REPORT, 'utf8'));
const zeroAttempt = JSON.parse(fs.readFileSync(process.env.REVIEW_CAPACITY_ZERO_REPORT, 'utf8'));

test('prepares verified API report metadata without modifying the payload', () => {
  const before = JSON.stringify(attempt);
  const prepared = projection.prepareReport(attempt);
  assert.deepEqual(prepared.inputs, attempt.report.inputs);
  assert.deepEqual(prepared.manifest, attempt.manifest);
  assert.equal(prepared.horizon, 60);
  assert.equal(prepared.endTick, 198);
  assert.equal(JSON.stringify(attempt), before);
  const nullable = structuredClone(attempt);
  nullable.report.policies[0].horizon.latency.p50 = null;
  assert.equal(projection.prepareReport(nullable).policies[0].horizon.latency.p50, null);
});

test('projects the fixed comparison at tick 60 from saved data', () => {
  const prepared = projection.prepareReport(attempt);
  const actual = prepared.policies.map((policy) => {
    const view = projection.snapshot(policy, 60);
    return [
      view.counts.decided,
      view.counts.pending,
      view.counts.queued,
      view.counts.awaiting_review,
      view.counts.wip,
    ];
  });
  assert.deepEqual(actual, [[6, 18, 16, 0, 2], [8, 16, 0, 15, 16], [8, 16, 13, 1, 3]]);
  assert.deepEqual(
    prepared.policies.map((policy) => policy.drain.end_tick),
    [198, 152, 152],
  );
});

test('uses inclusive timestamp transitions and conserves all tasks', () => {
  const policy = projection.prepareReport(attempt).policies[0];
  for (const tick of [0, 2, 8, 14, 20, 198]) {
    const view = projection.snapshot(policy, tick);
    assert.equal(
      view.counts.not_arrived + view.counts.queued + view.counts.wip + view.counts.decided,
      24,
    );
    assert.equal(view.counts.wip, view.counts.executing + view.counts.awaiting_review + view.counts.reviewing);
  }
  assert.deepEqual(projection.snapshot(policy, 0).groups.executing, [0]);
  assert.deepEqual(projection.snapshot(policy, 8).groups.reviewing, [0]);
  assert.deepEqual(projection.snapshot(policy, 14).groups.decided.slice(0, 1), [0]);
  assert.deepEqual(projection.snapshot(policy, 198).groups.decided, Array.from({ length: 24 }, (_, i) => i));
});

test('handles future arrivals and null timestamps as not yet transitioned', () => {
  const policy = {
    name: 'partial',
    tasks: [
      { task_id: 10, arrival_tick: 0, admission_tick: 0, ready_tick: null, review_start_tick: null, decision_tick: null },
      { task_id: 11, arrival_tick: 4, admission_tick: null, ready_tick: null, review_start_tick: null, decision_tick: null },
    ],
  };
  const view = projection.snapshot(policy, 2);
  assert.deepEqual(view.groups.executing, [10]);
  assert.deepEqual(view.groups.not_arrived, [11]);
  assert.equal(view.counts.pending, 2);
});

test('builds right-continuous step vertices and extends through the drain', () => {
  assert.deepEqual(
    projection.stepPoints([{ tick: 0, decided: 0 }, { tick: 4, decided: 2 }, { tick: 7, decided: 3 }], 'decided', 10),
    [[0, 0], [4, 0], [4, 2], [7, 2], [7, 3], [10, 3]],
  );
  const saved = projection.prepareReport(attempt);
  const actualSamples = saved.policies[0].samples;
  const points = projection.stepPoints(actualSamples, 'decided', saved.endTick);
  assert.deepEqual(points[0], [0, actualSamples[0].decided]);
  assert.deepEqual(points[points.length - 1], [saved.endTick, actualSamples.at(-1).decided]);
});

test('rejects malformed report shapes and unsafe logical ticks', () => {
  for (const payload of [null, {}, { ...attempt, report: { ...attempt.report, inputs: { ...attempt.scenario, observation_horizon: 1.5 } } }]) {
    assert.throws(() => projection.prepareReport(payload));
  }
  assert.throws(() => projection.snapshot({ tasks: [] }, Number.MAX_SAFE_INTEGER + 1));
});

test('supports zero horizon and incomplete drains with an explicit endpoint', () => {
  const prepared = projection.prepareReport(zeroAttempt);
  assert.equal(prepared.horizon, 0);
  assert.equal(prepared.endTick, 1);
  assert.equal(prepared.policies[0].horizon.queue_means.queued, null);
  assert.equal(prepared.policies[0].drain.complete, false);
  assert.equal(prepared.policies[0].drain.pending, 24);
  assert.equal(prepared.policies[0].drain.decided, 0);
  assert.equal(prepared.policies[0].drain.makespan, null);
});
