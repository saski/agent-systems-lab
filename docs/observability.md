# Activity, telemetry and history

When work is waiting, telemetry may also be waiting for delivery. This guide
teaches you to read those as separate states, then explains what history checks
can establish about recorded events and what they cannot establish about
process health or administrators. For a tour of each interface module, see the
[illustrated dashboard guide](dashboard.md).

The **Activity** view reads events recorded by the gateway during workflow
execution. The separate **Experiments** view reads saved reports from the
numerical Review Capacity simulation. The first describes recorded application
activity; the second describes model results.

## Start the activity dashboard

```sh
make dashboard
```

Open <http://127.0.0.1:8765/dashboard>. Connect using the read-only credential in
`.lab/viewer.token`. The browser holds it only in memory; reload requires
reconnecting. Do not share the operator credential. The viewer can read activity
and integrity information, but cannot create runs, grant access, approve or revoke.

In another terminal, run through that persistent gateway:

```sh
make dashboard-demo
```

The dashboard shows the fixture workflow, its specialists and current stage,
an event timeline, chain verification and telemetry delivery backlog. It also
shows older local runs. These records describe the workflow shown by the
gateway; they do not establish worker process health. The dashboard does not
launch workers or make operator decisions.
Task-state counts cover all recorded runs; the selectable list shows the latest
100. Workflow age starts at run creation; review wait starts at `run.ready`.
Telemetry pending count and oldest pending age describe a separate delivery
queue. Missing or invalid ages remain unknown. The two session charts keep up
to 120 readings in browser memory, preserve gaps after failed reads, and reset
on reload or a new viewer session. They are not persistent historical charts
or the Review Capacity simulation.
Polling resumes from a sequence cursor, the last event number received, and
deduplicates repeated batches. A failed connection is displayed as stale and
stops live animation. A worker with no terminal event after 120 seconds is
unknown, not assumed healthy. Revocation means access was revoked; it does not
prove that the OS process has stopped.

`make demo` still uses a temporary local gateway and the same SQLite database.
`make dashboard-demo` makes the browser and workers share the persistent gateway.
Container users open the same dashboard URL after `make containers-up`, then use
`make containers-demo`. SQLite and Compose/Postgres are separate histories.

## What history guarantees

Every new event and its operational state change commit in one database
transaction. Globally sequenced events carry stable event IDs, trace/span IDs,
actor, run, outcome, timestamp, provenance (where the record came from) and a
SHA-256 link to the previous event. SHA-256 is a hash function that produces a
fixed-size fingerprint of the event content.
The final head is stored separately. SQL triggers are automatic database rules
that reject updates, deletes and replacement of history; Postgres also rejects
truncation. The gateway exposes no API to rewrite or delete recorded events.

Lifecycle event keys deduplicate exact retransmission, even after restart.
Conflicting content under the same identity is rejected. Repeated model/tool
requests are distinct attempts and remain visible. This is **not** general
exactly-once task execution or automatic deduplication of arbitrary HTTP POSTs.

The additive migration keeps the previous `events` table, seals it, and copies its
records once into the journal, retaining their IDs and timestamps and marking
`legacy_import`. The chain only establishes integrity from import onwards.
Migration never deletes or resets experiment state. Back up important state before
an upgrade; a running older gateway must be stopped before switching versions.

Operational run rows, local JSON exports, dashboard projections and telemetry
acknowledgements are mutable views. The canonical journal is the historical
source: it records the events against which those views can be checked.
Neither a database administrator nor a host administrator is excluded by this
local setup: they can disable SQL triggers and rewrite the database, including
all hashes. A chain on the same machine is not write-once, read-many (WORM)
storage or a signature.

## Verify and keep an independent checkpoint

```sh
make history-check
uv run systems-lab history-checkpoint --output /path/to/new-checkpoint.json
uv run systems-lab history-verify --checkpoint /path/to/new-checkpoint.json
```

The checkpoint command uses exclusive creation: an existing file is never
replaced. Store a copy in a separately administered, versioned or WORM location.
The verifier checks the entire current chain and that the older checkpoint's
sequence/hash is still present. Later legitimate events remain valid. Truncation
or rewriting before the checkpoint is detectable against that trusted copy.
A local unprotected copy alone does not prevent a privileged attacker replacing
both the database and the checkpoint. External anchoring is an operator step,
not an already configured cloud service.

The dashboard accepts a saved checkpoint JSON file, up to 16 KB, for a read-only
comparison through `/history/verify`. It checks the current chain and the saved
sequence/hash; an older checkpoint can match after new events. Invalid files,
mismatches and unavailable comparisons are separate states. A reload, lock or
new file clears the earlier comparison. The interface does not create an
independent trusted copy for you. SHA-256 hashes do not encrypt events, and this
implementation does not sign events or automatically anchor them outside the
database.

For Compose, add `--gateway http://127.0.0.1:8765` before the history command to
inspect the Postgres history rather than the local SQLite history.

## OpenTelemetry scope and delivery

OpenTelemetry exports spans, timed records of gateway-observed operations, for
run, grant, authorization, worker lifecycle, tool/model completion, artifact
and human-decision events.
Each run has one trace ID to group its spans. Event and span IDs remain stable
across retransmission.
Completion events include measured operation duration; worker duration is observed
from its start and terminal events. Spans do not expose private reasoning or
claim to capture every function or CPU activity inside a worker.

A persistent delivery outbox, a queue of records awaiting export, is committed
with each event. The outbox holds records until the exporter reports successful
delivery; only that acknowledgement marks a batch delivered. The collector is
the service that receives exported telemetry. If it is unavailable, the outbox
retains the batch for later attempts, including after process restart. No
collector network call occurs inside the authorization/state-change transaction.
Integrity failure halts export. Delivery is **at least once**: a crash after
receiver acceptance but before local acknowledgement may resend a span. Stable
IDs help downstream correlation; downstream deduplication depends on that
backend. The dashboard uses the journal, so collector retries never duplicate
canonical history.

There is no network exporter by default. Configure
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` with the complete OpenTelemetry Protocol
(OTLP) over HTTP traces endpoint to enable it. Credentials, prompts, tool
arguments, response bodies and scenario contents are not exported. Export is an
explicit destination choice; configure
a trusted receiver before enabling it. One gateway/exporter process per database
is the supported playground topology. A new destination does not automatically
re-export already acknowledged history.

To start the Compose gateway, Postgres and a local Collector together:

```sh
make telemetry-up
make containers-demo
# Stop them without removing data volumes:
make telemetry-down
```

To use that receiver with the local SQLite gateway, run the Collector alone,
then start the dashboard with the explicit loopback endpoint:

```sh
docker compose --profile observability up -d otel-collector
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:4318/v1/traces make dashboard
```

Do not run the Compose gateway and a local dashboard on port 8765 simultaneously.
The checked-in Collector configuration uses the `observability` profile. A small
image layer prepares a directory owned by the Collector user (10001). The file
exporter appends across restarts. Its output file is a troubleshooting copy, not
immutable storage. OTLP acceptance is not a guarantee of permanent downstream
retention; the canonical history remains in the database.

## Sources and limits

The integration follows the OpenTelemetry [Python exporter documentation](https://opentelemetry.io/docs/languages/python/exporters/),
[public trace SDK](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.html)
and [Collector resiliency guidance](https://opentelemetry.io/docs/collector/resiliency/).

SQLite uses write-ahead logging (WAL) with read snapshots so dashboard scans do
not reserve its writer slot; ledger writers still serialize sequence allocation.
Full-chain verification and live projections deliberately prioritize clarity
over scale in this single-operator playground. The run overview is limited to the
latest 100 runs; historical events have stable cursors. Multi-tenant access,
external WORM anchoring, horizontally scaled exporters, configurable retention,
host metrics and production-grade database roles are future extensions.
