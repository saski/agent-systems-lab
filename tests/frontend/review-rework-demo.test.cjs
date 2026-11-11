const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const demo = require('../../docs/graphics/review-rework/replay.js');
const report = JSON.parse(fs.readFileSync(process.env.REVIEW_REWORK_REPORT, 'utf8'));

test('all displayed stocks match the saved model at every logical tick', () => {
  for (const policy of report.policies) {
    for (let tick = 0; tick <= 192; tick++) {
      const view = demo.snapshot(policy, tick);
      const sample = policy.samples.findLast(sample => sample.tick <= tick);
      for (const key of ['not_arrived', 'waiting_execution', 'executing', 'awaiting_review', 'reviewing', 'accepted', 'unfinished']) {
        assert.equal(view[key], sample[key], `${policy.name} ${tick} ${key}`);
      }
    }
  }
});

test('a change request keeps the last task unfinished through correction and rereview', () => {
  const task = report.policies[1].tasks[23];
  assert.equal(demo.stateAt(task, 181).state, 'reviewing');
  assert.deepEqual(demo.stateAt(task, 182), { state: 'executing', attempt: 2 });
  assert.deepEqual(demo.stateAt(task, 186), { state: 'reviewing', attempt: 2 });
  assert.equal(demo.stateAt(task, 192).state, 'accepted');
  const view = demo.snapshot(report.policies[1], 182);
  assert.equal(view.reviewing, 0);
  assert.equal(view.awaiting_review, 0);
});

test('the paired view retains winners, delayed tasks and unchanged tasks', () => {
  const changes = demo.outcomes(report);
  assert.deepEqual(changes, { earlier: 5, later: 15, unchanged: 4 });
  assert.equal(report.policies[0].tasks[7].accepted_tick, 164);
  assert.equal(report.policies[1].tasks[7].accepted_tick, 74);
  assert.equal(report.policies[0].tasks[22].accepted_tick, 152);
  assert.equal(report.policies[1].tasks[22].accepted_tick, 176);
});

test('timeline segments exactly cover arrival through acceptance, including both reviews', () => {
  for (const policy of report.policies) {
    for (const task of policy.tasks) {
      const segments = demo.segments(task);
      assert.equal(segments[0].start, task.arrival_tick);
      assert.equal(segments.at(-1).end, task.accepted_tick);
      assert.equal(segments.filter(segment => segment.state === 'reviewing').length,
        task.needs_correction ? 2 : 1);
      for (let i = 1; i < segments.length; i++) {
        assert.equal(segments[i - 1].end, segments[i].start);
      }
      assert.equal(segments.reduce((total, segment) => total + segment.end - segment.start, 0), task.turnaround);
    }
  }
});

test('inconsistent saved counts stop replay instead of displaying a false state', () => {
  const broken = structuredClone(report.policies[0]);
  broken.samples.find(sample => sample.tick === 60).accepted++;
  assert.throws(() => demo.snapshot(broken, 60), /reconcile/);
});
