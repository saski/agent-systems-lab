# fixture-workflow-admission Specification

## Purpose
Study whether two fixed fixture tasks can share one admitted place per batch
while preserving each run's identity across repeated commands and restarts.
The admitted task keeps its place while waiting for a person's decision, which
must match the digest of the reviewed material. Recovery blocks further work
when worker state is uncertain. These observations come from local workflow
processes; keep them separate from synthetic queue results and claims about
live-model or human review quality.

## Requirements

### Requirement: bounded fixture-workflow batch

The system SHALL provide an operator-created FIFO batch of exactly two tasks
using copies of the existing bounded backlog fixture scenario, with admitted
WIP fixed at one. It SHALL reuse existing specialist roles, scripted model
responses, gateway permissions and budgets. The gateway SHALL load the fixed
fixture itself and reject arbitrary scenarios, task lists, paths or WIP limits.
The admission cap SHALL apply per batch within one trusted local POSIX state
root and SQLite gateway; it SHALL NOT imply a global or distributed scheduler.
It SHALL preserve compatibility with existing single-run commands.

#### Scenario: queue the second fixture task

- GIVEN two tasks are queued in the initial batch
- WHEN the first is admitted and reaches `awaiting_review`
- THEN it retains the only admitted place
- AND the second task has no canonical run or worker

#### Scenario: reject unsupported batch creation

- GIVEN a gateway has no configured local admission coordinator
- WHEN an operator requests a batch
- THEN creation is rejected before a batch or run is persisted

### Requirement: durable single-owner admission

The system SHALL persist batch/item identity, queue order, ownership and run
bindings. Reservation, canonical run creation and item binding SHALL commit
atomically and be idempotent for retries. Competing or stale owners SHALL NOT
create duplicate runs or exceed the cap.

#### Scenario: retry after a lost admission response

- GIVEN an admission transaction committed but its response was lost
- WHEN the same item is advanced again
- THEN the existing run binding is returned without creating another run
- AND the binding retry itself dispatches no worker
- AND an uncertain prior launch stays blocked until reconciliation

#### Scenario: two owners request the only place

- GIVEN two independently connected owners attempt to advance the same batch
- WHEN their requests compete for admission
- THEN at most one run is admitted and the stale or competing owner is rejected

#### Scenario: prevent an owner takeover from racing a workflow launch

- GIVEN the prior owner or its workers may still be active
- WHEN a new owner attempts to invoke the batch workflow
- THEN no invocation is permitted until prior-owner exit and worker cleanup are confirmed
- AND Store fencing alone is not treated as proof that an earlier launch stopped

#### Scenario: the coordinator dies while its child remains alive

- GIVEN a child process inherited the batch lock descriptor
- WHEN the coordinator exits before the child
- THEN the child continues to exclude takeover until it exits
- AND the recovered launch intent still requires explicit reconciliation

### Requirement: human review retains admitted WIP

The system SHALL count reservations, active workflows, human-review waits and
uncertain admitted items against WIP. It SHALL release a place once only after
observing a canonical terminal outcome and confirmed worker cleanup where needed.
It SHALL NOT infer completion from a process exit, export file or checkpoint
interrupt, nor release capacity merely because ownership expires.

#### Scenario: observe an explicit manual decision

- GIVEN the first run awaits review and holds the only place
- WHEN an operator records an accepted or rejected outcome with the exact digest
- THEN reconciliation permits exactly one admission of the second task
- AND the completed first run's artifacts and worker count are preserved

#### Scenario: unavailable or revoked work

- GIVEN an admitted run cannot be read or its worker termination is uncertain
- WHEN the batch is advanced or its owner changes
- THEN it remains blocked and counts against WIP until safely reconciled
- AND it is not automatically retried or re-admitted

#### Scenario: explicitly reconcile an ambiguous terminal run

- GIVEN an ambiguous item has a canonical terminal outcome
- WHEN the operator reconciles it after obtaining process exclusion
- THEN its place is released exactly once
- AND reconciliation itself does not launch the next queued item

### Requirement: authorized decisions and isolated checkpoints

The system SHALL require operator authorization for batch reads and writes and preserve
the existing digest-bound manual decision flow. Each item SHALL have a distinct
run/checkpoint identity. Resume SHALL NOT bypass authorization, repeat completed
specialists at a human-review checkpoint or mix another task's state.

#### Scenario: restart while awaiting review

- GIVEN the first run is paused at its human-review checkpoint
- WHEN the admission owner restarts and advances the batch
- THEN it reuses that run and checkpoint without repeating completed specialists
- AND the second task stays queued until a valid terminal outcome

#### Scenario: reject unauthorized progress

- GIVEN a viewer, worker or operator with a stale artifact digest requests progress
- WHEN it attempts an unauthorized batch write or invalid decision
- THEN the request is rejected without releasing WIP or launching the next task

### Requirement: separate fixture runtime evidence

The experiment SHALL state its hypothesis, boundary and recovery limits, and
record actual queue/run/worker outcomes with fixture provenance and operational
timestamps. It SHALL NOT mix them with synthetic Review Capacity reports or
claim live-model quality, human productivity or a tick-to-second conversion.

#### Scenario: inspect the first runtime experiment

- GIVEN the isolated two-task fixture demonstration has completed
- WHEN its evidence is documented
- THEN admission, human-review waiting and manual outcomes reconcile by identity
- AND observations remain separate from the v0.2 numerical traces
