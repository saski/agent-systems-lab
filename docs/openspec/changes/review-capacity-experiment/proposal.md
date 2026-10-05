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

Status on 5 October 2026: partially implemented in the working branch. The
numerical model, CLI and exclusive report exports are available, with 50 passing
model/export/CLI tests. The fixed comparison has been rerun and documented in an
illustrated guide with a standalone, frozen documentation replay. The integrated
Experiments API/dashboard, Make demo target and complete v0.2 validation remain
pending. The learning guide does not complete the product-dashboard acceptance
scope. Scenario values are selected teaching inputs, not measured agent demand.

## Planning Validation

On 4 October 2026, `make spec-check` accepted the change and all three existing
specifications. `make check` passed lint, formatting, 33 existing tests and
Compose configuration validation; five container tests were skipped. The first
sandboxed test attempt could not bind localhost sockets; the successful rerun
used the same checks with local-server permission. These checks validate the
proposal format and existing repository behavior, not the unimplemented model.
