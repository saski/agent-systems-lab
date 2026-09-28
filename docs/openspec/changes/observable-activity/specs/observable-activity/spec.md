## ADDED Requirements

### Requirement: append-only attributable history
The gateway SHALL commit canonical sequenced audit events atomically with
operational changes, reject SQL mutation of journal records, and verify a
SHA-256 chain and persisted head. It SHALL preserve and label legacy audit events.

#### Scenario: historical mutation is rejected
- GIVEN a recorded event
- WHEN a database client attempts to update or delete that event normally
- THEN the operation fails and history remains unchanged

#### Scenario: a privileged alteration is detected against an external checkpoint
- GIVEN a previously exported checkpoint kept outside the database
- WHEN a changed or truncated history is verified against that checkpoint
- THEN verification fails
- AND documentation states that full privileged rewriting cannot be excluded without an independent anchor

### Requirement: idempotent lifecycle recording
The gateway SHALL deduplicate identical lifecycle events using stable keys and
reject conflicting reuse, while recording distinct authorized calls separately.

#### Scenario: duplicate completion survives restart
- GIVEN a worker completion was committed
- WHEN the same completion is retried after restart
- THEN exactly one canonical completion remains

### Requirement: recoverable OpenTelemetry delivery
The system SHALL export gateway-observed events as correlated OpenTelemetry
spans through a persistent outbox when explicitly configured, retaining stable
IDs across retries and omitting credentials and request bodies.

#### Scenario: collector outage and recovery
- GIVEN the collector is unavailable
- WHEN a task generates events
- THEN the task and journal continue and pending deliveries remain durable
- AND after recovery delivery retries use the original IDs

### Requirement: live read-only activity dashboard
The system SHALL show components, runs, agent states, workflow stages and an
event timeline from authenticated journal-backed data, with cursor recovery,
reduced-motion support and explicit stale/offline state. Viewer credentials
SHALL NOT authorize operational writes.

#### Scenario: running task advances and waits for review
- GIVEN a connected dashboard and a running task
- WHEN agents finish and the task reaches human review
- THEN the corresponding stages and activity display update
- AND recorded history can be inspected without changing the task

#### Scenario: a connection is interrupted
- GIVEN a previously connected dashboard
- WHEN polling fails
- THEN the dashboard marks the view stale and stops presenting animation as live
- AND reconnecting resumes from the event cursor without duplicating events
