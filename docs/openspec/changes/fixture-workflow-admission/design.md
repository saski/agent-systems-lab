# Fixture-workflow admission design

Proposed design; no runtime admission controller exists yet.

## Existing Interfaces and Missing Behavior

`cli.execute` currently creates one run through `ControlClient`, invokes
`workflow` with `thread_id=run_id`, and exports the gateway snapshot. The graph
runs three specialist processes, validates their artifacts, marks the run ready
and pauses for human review. The existing `decide` command verifies a matching
local checkpoint and digest before recording an operator decision and resuming.

`Store` owns canonical run status, artifacts, permissions and journal events.
LangGraph checkpoints live separately in SQLite. Worker execution failures and
timeouts revoke the run. Existing workflow tests cover resume at human review
without repeating specialists, but not batch admission or concurrent owners.

These interfaces can be reused; a durable queue, ownership, reservations and
idempotent run binding must be added. Neither a synthetic WIP limit nor distinct
thread IDs supplies those controls by itself.

## Boundary and Identity

The first batch contains exactly two copies of the existing bounded backlog
fixture scenario. It uses a separate local lab state directory and gateway,
the process executor and WIP one. An operator requests each advance; there is
no polling daemon or automatic decision loop.

Use a batch ID and stable item IDs distinct from canonical run IDs. Each item
maps to at most one run. Preserve `thread_id=run_id` for compatibility with the
existing decision CLI; different runs must have different checkpoint threads.
The batch ID must never become a shared workflow thread ID.

Keep canonical batch/item/reservation state in additive tables in the existing
Store database. Creating a run, reserving its place and binding its item identity
must commit in one transaction with a stable retry key. A lost response followed
by a retry must return the existing binding. Do not add an independently committed
queue database whose mapping can diverge from canonical run creation.

Checkpoint writes remain outside that transaction. On an ambiguous crash between
worker activity and a checkpoint, retain the place and block automatic execution
until the operator reconciles the run. Do not claim arbitrary exactly-once
worker execution from checkpointing alone.

## Admission and Recovery

One fenced owner may advance a batch. Transactional conditional updates and
unique identities must reject stale or competing Store writes; an in-process
mutex alone is insufficient. Test two independent connections against SQLite.

The Store fence does not make an external process launch atomic. For this local
slice, hold an exclusive process lock across the full advance/graph invocation
and check the current owner epoch at the launch boundary. Takeover may invoke
only after the previous owner has exited and its active workers are confirmed
absent or stopped. Unknown liveness blocks takeover execution. Test this with
competing coordinator processes, not only database connections.

Persist launch intent before invoking the graph. Retrying the run-binding
operation returns metadata only; it does not itself dispatch workers. If a prior
launch may have started, block until reconciliation rather than claiming
exactly-once execution. Owner expiration or takeover never releases admitted work.

Count reservations, running workflows, `awaiting_review` workflows and blocked
items with uncertain outcomes against WIP. Queueing before admission stays
visible. At WIP one, task two receives no run or worker while task one occupies
the place.

Read canonical gateway status before reconciling the queue. `accepted` and
`rejected` release a place once; `revoked` can release it only after worker
termination or absence is confirmed. An HTTP error, missing run, failed worker
or stale snapshot cannot stand in for that confirmation. Existing worker errors
lead to revocation; this proposal does not invent a new canonical `failed` state.

Restart at the human interrupt must reuse the existing run and checkpoint,
without repeating specialist processes. After an ambiguous in-flight failure,
show the affected item as blocked and require explicit operator reconciliation;
never automatically retry or re-admit a revoked item.

## Trust and Evidence

Queue creation and advance operations require operator authorization. Viewer and
worker credentials cannot reserve work, launch runs or decide outcomes. The owner
is trusted orchestration; no specialist persona or model output grants authority.
Keep credentials out of queue exports and worker configuration.

Preserve the existing digest-bound manual decision path. Batch progress reads
its result; it never submits a synthetic acceptance. No new specialist tool,
provider route, permission expansion or external write is needed.

Record actual admission/worker/decision observations with run and item identities,
fixture provenance and operational timestamps. Preserve them under ignored local
storage and distinguish canonical events from derived batch exports. Do not
write runtime observations into numerical reports or compare wall time directly
with synthetic ticks.

## Acceptance and Later Work

Use a minimal two-task behavior test first, then verify the real three-process
fixture graph through review, restart and explicit operator decisions. Cover
lost admission responses, competing owners, stale digests, permission denials,
revocation, worker failure and gateway unavailability. Retain single-run and
synthetic report regressions.

Only after this slice meets its contract should a separate proposal introduce
WIP above one, parallel worker scheduling, SQLite contention under that load or
container execution. Quality/rework and live-model evaluation require their own
hypotheses and evidence.
