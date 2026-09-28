# Design

The gateway remains the authority. Every new operational event is appended in the
same transaction as its state change. A globally serialized ledger head assigns
sequence numbers. SHA-256 links cover canonical JSON including event identity,
run, actor, timestamp, decision, provenance and trace IDs. SQL triggers reject
updates/deletes (and Postgres truncation). Existing events are copied once with
legacy-import provenance and their original timestamps/IDs; this does not prove
integrity before import. The old table is retained and sealed.

Lifecycle keys deduplicate exact retries. Reusing a key with different content
fails. Genuine repeated calls remain separate events. The journal is not a general
HTTP exactly-once guarantee. Operational snapshots are projections, not the audit
source. Verification compares the chain and head and can check a previously
exported checkpoint. A privileged database administrator can remove triggers and
rewrite a complete chain; checkpoints need an independent trusted location for
that threat. No WORM storage or external signing service is claimed.

A mutable outbox, committed with events, records OTLP delivery independently.
Retries keep event/trace/span IDs; OTLP remains at-least-once and the destination
may contain duplicate deliveries. Collector unavailability cannot erase history
or prevent a workflow. The default has no network telemetry export; an explicit
OTLP/HTTP endpoint enables it. Spans describe gateway-observed activity, not CPU,
all Python calls or model reasoning. Sensitive request bodies and tokens are omitted.

A small same-origin static dashboard uses authenticated cursor polling, with a
separate read-only viewer credential, live/replay distinction, stale-state handling,
reduced motion and no external assets. Ledger-derived stages are displayed along
with integrity and telemetry backlog. No browser controls grant permissions or
approve tasks. Local serving binds loopback; container gateway exposure remains
loopback on the host.
