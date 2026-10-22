# Design

The gateway remains the authority. Its journal is the ordered record of what
happened to each run. Every new event is appended in the same database
transaction as its state change, so the event and state cannot be committed
separately. A single serialized ledger head assigns sequence numbers. SHA-256
hashes link each event's canonical JSON to the history, covering its identity,
run, actor, timestamp, decision, source label (provenance) and trace IDs. SQL
triggers reject updates/deletes (and Postgres truncation). Existing events are
copied once with a `legacy_import` source label and their original timestamps
and IDs; this does not prove their integrity before import. The old table is
retained and sealed.

Lifecycle keys deduplicate exact retries. Reusing a key with different content
fails, while genuine repeated calls remain separate events. This protects the
journal's event recording; it is not a general HTTP exactly-once guarantee.
Operational snapshots are mutable views of current state, separate from the
journal's audit history.
Verification compares the hash chain and its current head and can check a
previously exported checkpoint. A privileged database administrator can remove
triggers and rewrite a complete chain, so a checkpoint must be kept somewhere
independent and trusted to detect that threat. The design does not claim Write
Once Read Many (WORM) storage or an external signing service.

An outbox is a set of mutable delivery records committed with the journal
events. It tracks which event observations still need acknowledgement from the next
receiver; it does not hold work for the agents to execute. The OpenTelemetry
Protocol (OTLP) exporter retries those records with the same event, trace and
span IDs. Delivery is at least once, so a destination may receive duplicates.
Collector unavailability cannot erase journal history or prevent a workflow.
The default has no network telemetry export; an explicit OTLP/HTTP endpoint
enables it. Spans describe activity observed by the gateway, not CPU use, every
Python call or model reasoning. Sensitive request bodies and tokens are omitted.

A small static dashboard served from the same origin as the gateway uses a
separate read-only viewer credential. It asks for events after its last cursor,
distinguishes live activity from replay, marks stale data, supports reduced
motion and loads no external assets. It displays workflow stages derived from
the journal, its integrity status and telemetry backlog. No browser control
grants permissions or approves tasks. Local serving binds to loopback; container
gateway exposure remains loopback on the host.
