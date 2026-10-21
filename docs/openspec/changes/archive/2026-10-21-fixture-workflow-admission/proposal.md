# Fixture-workflow admission

Status: implemented on 21 October 2026 after explicit user authorization.
Live providers and automatic human decisions remain outside this change.

## Why

[Review Capacity v0.2 is closed](../2026-10-20-review-capacity-experiment/verification.md).
Its synthetic model shows that a task keeps its
admitted-WIP place while waiting for review, but it does not schedule actual
LangGraph workflows. At proposal time, the CLI launched one run at a time and
had no durable admission owner or queue.

Before comparing concurrent runtime policies, test the smallest operational
boundary: can one fixture workflow retain its place through a human interrupt
while a second task remains queued, including after a coordinator restart?

## What Changes

- Add a finite local batch of exactly two tasks using copies of the existing
  backlog fixture scenario, with admitted WIP fixed at one for initial acceptance.
- Give batch items durable identities and FIFO positions. Create and bind each
  canonical run once through a single trusted admission owner.
- Reuse the existing specialist graph, worker budgets, checkpoints and gateway
  authorization. An `awaiting_review` run keeps the admission place.
- Let an operator explicitly advance the batch after inspecting and approving
  or rejecting the exact artifact digest through the existing decision flow.
- Guard workflow launch as well as Store writes against stale or competing
  owners; a new owner cannot invoke while the previous owner or its workers
  might still be active.
- Reconcile canonical outcomes and uncertain worker state before releasing
  capacity or resuming after interruption. Never infer completion from a CLI
  exit, an export file or the LangGraph interrupt alone.
- Export fixture provenance, queue transitions, identities and observed outcomes
  separately from the Review Capacity numerical reports.

## Hypothesis and Controlled Variables

With two fixed tasks and one admitted place, repeated advance commands and a
restart at human review will leave the second task queued until the first has
a canonical terminal outcome. Recovery will neither repeat completed specialists
nor create a second run for the same batch item.

Keep the backlog scenario, Researcher/Builder/Reviewer roles, scripted model
responses, tools and budgets constant. The initial intervention is the admission
rule; this is an operational correctness experiment, not a performance benchmark.

## First Acceptance Slice

1. Task one reaches `awaiting_review`; task two has no run or worker yet.
2. Repeating advance or restarting the owner preserves that state and the first
   run's identity, checkpoint, artifacts and completed-worker count.
3. A stale digest or unauthorized decision cannot release the place.
4. A valid manual accept or reject permits exactly one admission of task two.
5. Revocation and worker failure are exercised separately. Uncertain liveness or
   an unavailable gateway blocks admission until reconciliation is safe.

## Non-Goals

WIP above one, multiple simultaneous executions, Docker/Postgres acceptance,
distributed scheduling, background daemons, general task submission, live model
quality, automatic approval/retry/re-admission, external writes and dashboard
changes are outside this first slice. Review-quality/rework models remain a
separate possible numerical experiment. The telemetry-learning proposal is
independent and remains unimplemented.

## Impact

Implemented changes: an admission coordinator, additive Store tables/transactions,
operator-only gateway operations, CLI batch operations, workflow integration,
behavior/security tests and a dedicated fixture experiment guide. Existing
single-run commands and numerical report readers remain compatible.

Implementation started with the failing two-task admission test in `tasks.md`.
The fixed-fixture API, local CLI, recovery controls and evidence are documented
in `verification.md`. The cap is per batch; this is not a global scheduler.
