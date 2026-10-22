# Design

The detailed design, verified source references, alternatives, metric contracts,
failure matrix, learning slices and estimated effort are in the
[learning plan](../../../plans/2026-10-06-agent-telemetry-reliability-lab.md).
It is the design reference for this change; all runtime changes are proposed.

## Decisions

1. Use the existing fixture workflow and persistent gateway, independent of the
   dirty Review Capacity implementation. Preserve existing source changes.
2. Retain the lab Collector, the service that receives and forwards traces, as
   the stopped component in the outage exercise. Forward to the receiver in the
   local LGTM bundle used for Grafana, Tempo and Prometheus. Grafana and
   Prometheus must remain alive when the lab Collector stops.
3. Use OpenTelemetry metrics with a direct Prometheus scrape from an authenticated
   gateway endpoint. Prometheus reads the gateway's current snapshot directly, so
   metric freshness and Collector reachability do not depend on the stopped
   Collector's trace pipeline.
4. Derive current task counts from the gateway's canonical run state, never from
   received spans or delivery attempts. Keep metric labels to the fixed run-state
   values and deployment names; do not add a unique label for each run or event.
   This keeps the number of stored time series bounded as the lab runs more tasks.
   Distinguish a real zero from disabled export, failed reads and stale data.
5. Compare the unique event/span IDs in the gateway journal, the durable ordered
   record of task events, with a complete Tempo trace query for one small run.
   The outbox records events awaiting the next receiver's acknowledgement.
   Retries retain IDs, but OpenTelemetry delivery is at least once, so a receiver
   may see duplicates; a later gap can still occur after acknowledgement. Keep
   incomplete queries visible and make no production loss-detection or
   deduplication guarantee.
6. Keep host control, gateway permissions, worker isolation and human approval
   unchanged. The only fault exercise is an opt-in fixture case for one selected
   role/run: a fixed delay of at most five seconds or a controlled worker failure.
   It uses the normal gateway lifecycle and accepts no arbitrary command.

## Risks and mitigations

- **Bundled backend failure:** the observer can fail with the backend. Retain the
  original gateway dashboard and a host-side diagnostic; this local setup does
  not provide high availability (HA).
- **Post-acknowledgement loss:** the durable gateway outbox covers its own
  acknowledgement boundary. Finite reconciliation can reveal missing downstream
  spans; persisted Collector recovery remains deferred.
- **False interpretation:** event spans are not complete worker instrumentation;
  policy denial and human rejection are not inherently technical crashes;
  logical ticks are not seconds. Teach and test these distinctions.
- **Version drift:** pin tested image/SDK versions during implementation and
  verify provisioning paths, metric names, TraceQL and alert semantics.
- **Data leakage or authority expansion:** preserve explicit resources and
  attribute allowlists, viewer-only metrics, private networks and no operator
  credentials in observation services.
- **Existing work or runtime collision:** review both checkouts again before
  implementation; use additive files, explicit profile/ports and fresh evidence;
  do not reset histories, acknowledgement flags or other running services.

## Validation and rollback

Use failing behavior tests, then relevant unit tests, canonical repository checks
and an explicitly started opt-in integration suite. Inspect the actual UI and
document observed timing and missing checks. Existing specifications are not
synced or archived until the implementation meets the acceptance contract.

The optional profile can be stopped without removing data. Restore the prior
explicit exporter destination when leaving the exercise; do not replay previously
acknowledged history automatically. Preserve all run evidence and configuration
needed to reproduce the observation. No destructive cleanup is part of the demo.
