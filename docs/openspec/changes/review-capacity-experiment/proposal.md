# Review capacity experiment

## Why

The playground can show a workflow waiting for an operator, but it cannot yet
explain how execution capacity, review capacity and admission policy interact.
A reproducible comparison would connect technical controls to an engineering
leadership question: which intervention improves delivery when review is scarce?

The current backlog model is a numerical stock-and-flow model. The current
LangGraph workflow executes specialists sequentially within one run; the CLI
does not provide a workload scheduler. This proposal does not assume an existing
runtime queue or concurrency controller.

## What Changes

Propose version 0.2 as one bounded review-capacity experiment:

- Add a deterministic event-time model with finite arrivals, parallel execution
  slots, one synthetic reviewer, FIFO queues and optional total-WIP admission.
- Compare one execution slot, four slots, and four slots with WIP capped at three,
  keeping workload and review service fixed.
- Export scenario, event trace, reconciled metrics and provenance to fresh local
  attempt directories, with deterministic report hashes and no overwrites.
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

Status on 20 October 2026: Slices 1 and 2 are implemented. The numerical model, CLI,
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
configuration checks, with 5 opt-in container tests skipped; all 5 OpenSpec
items and the whitespace check passed. Desktop/mobile browser checks and
captures document the comparison and replay, loading, empty and error states,
reduced motion and read-only playback. Spec synchronization and archival remain
pending.

## Planning Validation

On 4 October 2026, `make spec-check` accepted the change and all three existing
specifications. `make check` passed lint, formatting, 33 existing tests and
Compose configuration validation; five container tests were skipped. The first
sandboxed test attempt could not bind localhost sockets; the successful rerun
used the same checks with local-server permission. These checks validate the
proposal format and existing repository behavior, not the unimplemented model.
