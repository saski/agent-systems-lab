# Observable activity and durable history

## Why
Operators need to see which specialist is working, where each task has reached
and whether its recorded history still verifies. A trace groups related
observations for inspection, but it does not by itself preserve a durable audit history. The
event journal provides that record; a retry outbox tracks which journal events
still need to reach the telemetry receiver.

## What Changes
- Add a transactionally written, append-only, hash-chained event journal with
  stable event identities, replay-safe lifecycle recording and external checkpoints.
- Preserve existing audit records through an additive, labelled import.
- Export canonical events to OpenTelemetry through a persistent retry outbox.
- Add a read-only animated browser dashboard with live workflow and system views.

## Impact
SQLite and Postgres stores, gateway, CLI, optional Compose observability service,
dependencies, tests and operator documentation. Existing worker capabilities and
fixture-only model access remain unchanged.
