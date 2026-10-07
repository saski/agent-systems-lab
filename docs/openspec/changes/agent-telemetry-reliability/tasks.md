# Implementation tasks

All tasks below are pending. User approval of implementation is required by the
task's explicit scope; this planning change does not provide it.

## Slice 0: understand the existing run

- [ ] Recheck both checkouts and current runtime/ports without replacing existing
      work; select the implementation baseline and reload applicable rules.
- [ ] With service execution authorized, record a fresh fixture run, trace ID,
      model mode, executor, artifact digest and human-review checkpoint.
- [ ] Have the learner predict and explain the checkpoint using existing evidence.

## Slice 1: query existing traces

- [ ] Select and record tested LGTM tag/digest and component versions; verify
      architecture support, local resource use, configuration paths and port availability.
- [ ] Add the optional Compose override, narrow telemetry network and lab-Collector
      forwarding configuration; preserve the existing file exporter/profile.
- [ ] Provision Tempo/Prometheus data sources and retain new runtime data under
      ignored `.lab/observability/`; add canonical Make start/stop/config-check targets.
- [ ] Verify effective Compose boundaries and a fresh run's IDs/timestamps in Tempo;
      have the learner inspect a worker completion and explain event-span limits.
- [ ] Verify override support and assert the resolved Collector has only the
      telemetry network and no host ports; neither observation service may retain
      database or worker network attachments through Compose merging.

## Slice 2: metrics with honest meanings

- [ ] Start with failing behavior tests for distinct run counts beyond 100 runs,
      resend/restart without count inflation, empty data versus failed reads,
      consistent snapshots, viewer authority and sensitive sentinel exclusion.
- [ ] Add the five aggregate OTel metrics and authenticated endpoint, using the
      smallest locked exporter dependency; no trace-derived task counts.
- [ ] Serve metric exposition through the viewer-protected FastAPI route, without
      a second unauthenticated listener; return a failed scrape on snapshot error
      and validate exporter registration/cleanup across app lifecycle.
- [ ] Configure direct Prometheus scraping with viewer credentials from a file
      and explicit Collector self-metric exposure only on the private network.
- [ ] Provision the compact dashboard with current states, backlog/age, enablement,
      freshness, target reachability and a trace lookup; preserve null/stale states.
- [ ] Have the learner write review-state, backlog and absence queries and explain
      why run IDs are excluded from metric labels.

## Slice 3: introduce and diagnose bounded failures

- [ ] Add failing behavior tests for fixture-only scoped delay/failure and reject
      unknown modes; exercise real lifecycle recording and permission enforcement.
- [ ] Add the bounded demo fault path without arbitrary execution or new permissions.
- [ ] Provision the single alert with its tested truth table, missing-series checks,
      No Data/Error handling and no external contact point.
- [ ] Test the alert for normal, review-pending, empty, disabled, delayed delivery,
      failed targets, partial missing series, whole-query absence and query error.
- [ ] Stop only the lab Collector, run a fixture, observe independent evidence and
      recover without clearing pending state; repeat with exporter restart.
- [ ] Add finite read-only span comparison with complete-query checks and a frozen
      journal boundary; fail on missing/partial evidence, tolerate duplicate IDs.
- [ ] Test acceptance followed by failed local acknowledgement and a controlled
      downstream omitted span even when the outbox is empty.
- [ ] Have the learner predict each intervention and explain two supporting facts
      and one limitation; document the full-LGTM failure boundary.

## Slice 4: demonstrate and hand over

- [ ] Add experiment/quickstart/demo guides with inputs, hypothesis, provenance,
      actual observations, timings and limits; label all unavailable checks.
- [ ] Reproduce dashboard and alert from files; inspect actual Grafana UI and
      original activity dashboard without exposing credentials or sensitive content.
- [ ] Add an opt-in integration Make target, then run it and the applicable existing
      container isolation tests with explicit service-start scope.
- [ ] Run `make check`, `make spec-check` and `git diff --check`; record results.
- [ ] Have the learner deliver the rehearsed three-minute demonstration and explain
      missing data versus zero, duplicate deliveries and a post-acceptance gap.
- [ ] Update user-facing links only for implemented functionality. Review completed
      evidence before syncing/archiving this change; no automatic publication.
