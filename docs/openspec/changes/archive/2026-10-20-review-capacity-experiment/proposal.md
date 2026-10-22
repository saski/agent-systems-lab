# Review capacity experiment

## Why

The playground can show one workflow waiting for an operator, but it cannot yet
show what happens when many tasks compete for execution and review. Here,
execution capacity means the number of tasks that can run in parallel; review
capacity is the rate at which the single modeled reviewer can decide; and the
admission policy controls how many tasks may enter while earlier work is still
unfinished. Comparing those controls makes the queueing tradeoff visible when
review is scarce.

The current backlog model is a numerical stock-and-flow model. The current
LangGraph workflow executes specialists sequentially within one run; the CLI
does not provide a workload scheduler. This proposal does not assume an existing
runtime queue or concurrency controller.

## What Changes

Propose version 0.2 as one finite, reproducible review-capacity experiment. Its
task count, service times and simulation horizon have fixed limits, so the
comparison stays small enough to inspect:

- Add a deterministic event-time model that advances in logical ticks, with
  finite arrivals, parallel execution slots, one simulated reviewer that accepts
  every task, first-in, first-out (FIFO) queues and optional total
  work-in-progress (WIP) admission.
- Compare one execution slot, four slots, and four slots with WIP capped at three,
  keeping workload and review service fixed.
- Save each run's scenario, event trace, reconciled metrics and a source label
  identifying the results as simulated in its own local attempt directory. A
  report hash, a fingerprint calculated from its contents, helps detect changes;
  repeated attempts never overwrite earlier files.
- Add a read-only Experiments view to the local dashboard: queue occupancy,
  cumulative simulated decisions, waiting times and an animated replay.
- Document predictions, actual observations after implementation, and limits.

The minimum publishable result is a reproducible comparison and a readable
dashboard capture explaining one observed tradeoff. A result that contradicts
the prediction is equally useful and must be reported honestly.

## Acceptance Scope

The v0.2 scope is the numerical model, CLI export, local dashboard replay,
behavior tests and documentation. The simulated reviewer does not approve real
agent runs. No simulated transition is written as a worker or operator event in
the canonical gateway journal or exported as a real workflow span.

A subsequent, separately scoped change may validate the admission policy against
actual fixture workflows. Real-model evaluation remains another experiment.

## Non-Goals

Live model access, new specialist tools, runtime replacement, a production task
queue, dynamic delegation, automated approval of ordinary runs, external writes,
or an immutable-storage guarantee for local report files. No broker, frontend
framework or plotting dependency is required.

## Impact

Expected implementation areas: a pure numerical module, `cli.py`, a bounded
read-only report reader in the local gateway, static dashboard assets, tests,
Make targets, `experiments/review-capacity/`, and operator documentation.
Existing specialist capabilities, permission enforcement, live activity and
human-decision semantics remain the reference boundaries.

Status on 20 October 2026: all three slices are complete and v0.2 is closed.
The numerical model, CLI,
exclusive report exports, fixed scenario and `make review-capacity-demo` target
are available. The target runs the locked CLI against
`experiments/review-capacity/scenario.json`. Observation horizon validation is
bounded to 0..10000 ticks; the drain deadline remains at most 50000 ticks. The
read-only Experiments HTTP API, access tests and integrated dashboard comparison
and replay are available. The API lists and loads
complete, hash-verified reports by attempt ID under the server-configured
`LAB_ROOT/.lab/experiments/review-capacity` directory. It uses the existing
viewer authorization, rejects worker credentials, and does not accept request
paths. Container report mounting remains unimplemented.
The dashboard projects saved transitions with local play/pause, seek, speed and
reduced-motion controls; it never executes a simulation or records operational
decisions. Scenario values are selected teaching inputs, not measured agent
demand. The standalone learning guide remains a complementary offline artifact.

The 20 October 2026 targeted frontend, API and Activity checks passed 49 tests.
Full validation passed Ruff, 131 tests and Compose
configuration checks, with 5 opt-in container tests skipped; all 5 pre-archive
OpenSpec items and the whitespace check passed. Desktop/mobile browser checks and
captures document the comparison and replay, loading, empty and error states,
reduced motion and read-only playback. OpenSpec synchronized all eight
requirements and archived this change on 20 October 2026. See `verification.md`
for the closure audit and fresh validation evidence.

## Planning Validation

On 4 October 2026, `make spec-check` accepted the change and all three existing
specifications. `make check` passed lint, formatting, 33 existing tests and
Compose configuration validation; five container tests were skipped. The first
sandboxed test attempt could not bind localhost sockets; the successful rerun
used the same checks with local-server permission. These checks validate the
proposal format and existing repository behavior, not the unimplemented model.
