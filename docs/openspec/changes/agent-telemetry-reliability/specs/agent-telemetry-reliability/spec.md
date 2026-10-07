## ADDED Requirements

### Requirement: local reproducible trace exploration
The experiment SHALL provide an opt-in, version-pinned local Tempo/Grafana
configuration for current gateway-observed OTLP spans, preserving the default
file-export path and gateway permission boundaries.

#### Scenario: follow a fresh fixture run
- GIVEN a newly created fixture run and the optional observation profile
- WHEN its pending telemetry is delivered
- THEN its journal trace and span identities are queryable in Tempo through Grafana
- AND original event times and fixture provenance are preserved
- AND the guide distinguishes event/completion spans from full worker instrumentation

#### Scenario: preserve existing evidence and isolation
- GIVEN existing local histories and the normal worker restrictions
- WHEN the optional profile is started and later stopped
- THEN no database, journal or telemetry data is deleted or silently replayed
- AND no worker receives new credentials, host mounts, Docker socket or network access
- AND only intended loopback ports are published
- AND resolved Compose configuration excludes observation services from database and worker networks

### Requirement: independent read-only metrics
The gateway SHALL expose authenticated, bounded-label OTel metrics for run state,
pending delivery count and age, exporter enablement and successful snapshot time.
Prometheus SHALL collect them without traversing the Collector delivery pipeline.

#### Scenario: count tasks independently of retransmission
- GIVEN distinct canonical runs, including more than the activity overview limit
- WHEN an observation is delivered repeatedly or the exporter restarts
- THEN metric run counts still equal current distinct run rows in that database
- AND IDs, hashes, actor instances and arbitrary text do not become metric labels

#### Scenario: preserve viewer authority
- GIVEN the read-only viewer credential used for metric collection
- WHEN it requests metrics or attempts to grant, decide or revoke a run
- THEN metrics can be read and operational writes remain unauthorized
- AND collection does not mutate canonical history
- AND no second unauthenticated metrics listener bypasses gateway viewer checks

### Requirement: explicit zero and missing-data semantics
Panels and alert evaluation SHALL distinguish successful zero values, disabled
export, missing series, stale snapshots and failed data-source queries.

#### Scenario: empty healthy lab
- GIVEN an enabled exporter, successful fresh database read and empty outbox
- WHEN the metrics are scraped
- THEN pending count and pending age are explicitly zero
- AND freshness evidence establishes why those zeros are meaningful

#### Scenario: failed or partial observation
- GIVEN a failed scrape, missing expected series or stale snapshot
- WHEN Grafana displays or evaluates the data
- THEN it indicates missing, stale or attention state as appropriate
- AND it does not substitute a healthy zero or silently retain a green state
- AND a surviving series cannot conceal a missing required series

### Requirement: meaningful local delivery alert
The experiment SHALL provision one local Grafana-managed alert rule for delivery
backlog, failed required scrape targets and stale snapshots, with explicit
No Data and Error behavior and documented evaluation timing.

#### Scenario: ingest Collector is stopped
- GIVEN the gateway, LGTM backend and direct scrape paths remain available
- WHEN only the lab Collector is stopped and a fixture run produces events
- THEN the task and journal continue independently
- AND pending delivery and failed Collector reachability are visible
- AND the alert enters attention within the documented test budget
- AND no external message or automatic operational action is sent

### Requirement: controlled fixture diagnosis
The experiment SHALL provide opt-in, bounded fault exercises that use the normal
gateway and worker lifecycle, without arbitrary commands or expanded authority.

#### Scenario: distinguish short delay from failure
- GIVEN a new fixture run with one selected Builder intervention
- WHEN a fixed delay or controlled nonzero worker exit occurs
- THEN measured worker completion duration or worker failure evidence identifies it
- AND normal failure handling retains run revocation and permission enforcement
- AND unknown fault modes and non-fixture use are rejected

#### Scenario: distinguish pending review from an incident
- GIVEN completed specialists and a run awaiting a digest-bound human decision
- WHEN observation paths are healthy
- THEN the UI identifies human review as the next step
- AND it does not classify waiting, human rejection or every policy denial as a technical failure
- AND Grafana cannot approve or resume the run

### Requirement: identity-preserving recovery and finite reconciliation
Recovery SHALL retain original event identities and timestamps, leave canonical
history unchanged by retries, and compare a bounded expected span set with
complete backend query results without assuming exactly-once receipt.

#### Scenario: recover a pending batch across exporter restart
- GIVEN an unavailable ingress Collector and durable pending journal events
- WHEN the exporter restarts with the same database and the Collector recovers
- THEN pending events become queryable with their original trace and span IDs
- AND the stored journal prefix and checkpoint still verify
- AND retransmission does not become a new task or canonical event

#### Scenario: receiver accepts before acknowledgement fails
- GIVEN a receiver accepted a batch but its local acknowledgement was not saved
- WHEN the gateway retries that pending batch
- THEN the repeated delivery retains the original identities
- AND the evidence comparison counts unique identities and reports receipt behavior honestly

#### Scenario: accepted evidence is missing downstream
- GIVEN a controlled receiver or filter omits one known fixture span after acceptance
- WHEN a bounded complete Tempo query is compared with expected journal identities
- THEN the missing identity is reported even if the gateway outbox is empty
- AND time range, query completeness and observation deadline are reported
- AND no claim of irreversible loss or automatic replay follows from that gap alone

#### Scenario: entire observation backend is unavailable
- GIVEN Grafana and Prometheus stop with the LGTM backend
- WHEN the operator diagnoses the missing view
- THEN the guide directs them to the independent gateway dashboard and host check
- AND it does not claim that the unavailable Grafana alert can detect its own outage

### Requirement: safe and honest learning evidence
The experiment SHALL preserve the telemetry allowlist and provide a hypothesis,
boundary, variables, observations, limits, learner exercises and reproducible
configuration, guide and demonstration.

#### Scenario: sensitive sentinels stay local
- GIVEN credentials, prompts, tool arguments, content and raw exception text in test inputs
- WHEN traces, metric samples and demo evidence are generated
- THEN none of those values appears in exported payloads, labels, panels or saved shared evidence
- AND an authentication credential appears only where required for transport access

#### Scenario: explain the outcome independently
- GIVEN completed learning slices
- WHEN the learner performs the prepared demonstration
- THEN they can query a run, predict and diagnose a fault, show recovery and explain a possible resend
- AND they distinguish observed wall time from Review Capacity logical ticks
- AND fixture evidence is not described as production performance or real-model quality
