# Observable activity and durable history

## Why
Operators need to see which agent is working, where each task stands, and whether
its history is intact. Traces alone do not establish a durable audit history.

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
