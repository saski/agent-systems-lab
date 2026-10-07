# Design

The detailed design, verified source references, alternatives, metric contracts,
failure matrix, learning slices and estimated effort are in the
[learning plan](../../../plans/2026-10-06-agent-telemetry-reliability-lab.md).
It is the design reference for this change; all runtime changes are proposed.

## Decisions

1. Use the existing fixture workflow and persistent gateway, independent of the
   dirty Review Capacity implementation. Preserve existing source changes.
2. Retain the lab Collector as the stopped component in the outage exercise.
   Forward to the receiver bundled with LGTM. Grafana and Prometheus must remain
   alive when that ingress Collector stops.
3. Use OTel metrics with a direct Prometheus scrape from an authenticated gateway
   endpoint. Neither application freshness nor Collector reachability depends
   exclusively on the stopped Collector's OTLP pipeline.
4. Derive current task counts from canonical operational state, never received
   spans or delivery attempts. Read-only aggregates have bounded labels and
   distinguish legitimate zeros, disabled export, failed reads and stale data.
5. Compare expected journal identities against complete Tempo trace results for
   one small run. At-least-once delivery, downstream gaps and query incompleteness
   stay visible; no production loss detection or deduplication guarantee is made.
6. Keep host control, gateway permissions, worker isolation and human approval
   unchanged. Only a scoped fixture demo path may inject bounded delay/failure.

## Risks and mitigations

- **Bundled backend failure:** the observer can fail with the backend. Retain the
  original gateway dashboard and a host-side diagnostic; do not claim HA.
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
