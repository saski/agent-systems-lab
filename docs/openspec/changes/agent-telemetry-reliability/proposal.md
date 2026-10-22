# Agent Telemetry Reliability Lab

## Why

A quiet activity screen can mean slow or failed execution, a legitimate human
review checkpoint, or interrupted telemetry. The gateway keeps an ordered,
durable journal of task events, and its outbox retries sending those events as
OpenTelemetry Protocol (OTLP) traces. The lab lacks a place to search those
traces and metrics that remain available independently of the Collector. The
exercise teaches how to use those separate signals to tell the three conditions
apart.

The primary outcome is learner understanding through a real fixture workflow,
queries and controlled failures. The [learning plan](../../../plans/2026-10-06-agent-telemetry-reliability-lab.md)
explains the baseline, options, exercises, sources, estimates and demonstration.

## What Changes

- Add an opt-in local LGTM observability bundle with Grafana to query and display
  results, Tempo to store traces, and Prometheus to collect metrics. Keep the
  existing lab Collector as an independently stoppable trace-ingestion hop.
- Add five read-only OpenTelemetry metric families, each grouping a measurement
  with its permitted labels, scraped directly by Prometheus. Also
  collect Collector health metrics directly, outside its own trace pipeline.
- Provision a compact Grafana dashboard and one local alert rule with explicit
  missing/stale/error behavior.
- Add opt-in fixture exercises with fixed, short delay or failure cases, then
  compare the expected event IDs for one run with the spans queryable in Tempo.
  The comparison reads evidence; it does not change the journal or outbox.
- Supply a startup guide, learner exercises, three-minute demo and limitations.

## Acceptance Scope

The acceptance path follows fresh fixture runs through normal execution, a
human-review pause, a short worker delay or failure, a stopped ingress Collector,
recovery and retransmission. Use one gateway/exporter per database. The journal
is the durable task history; the outbox tracks telemetry events awaiting
acknowledgement by the next receiver. Recovery must preserve journal history and
event identities. If an event is acknowledged by the Collector but is absent
from a complete Tempo query, the finite comparison should report its ID missing.
This does not establish permanent retention or automatic replay after
acknowledgement.

Metrics and Grafana remain observers. They gain no task-execution authority.
No Review Capacity logical ticks are exported as live workflow time.

## Non-Goals

Implementation in this planning task; production monitoring; Kubernetes; fleet
management; a new control plane; Grafana Cloud; public deployment; external
notifications; live/paid providers; worker credential/network expansion; automatic
approval; correlated application logs; full worker instrumentation; persistent
downstream recovery or general exactly-once delivery.

## Capabilities

### New Capabilities

- `agent-telemetry-reliability`: a local, reproducible observation and diagnosis
  experiment with independent delivery evidence and explicit learning checks.

### Modified Capabilities

None. Existing `observable-activity`, `governed-execution` and
`systems-experiments` requirements remain the baseline and must keep passing.

## Impact

Expected changes after approval: optional Compose/configuration/provisioning
files, narrow gateway metric reads, fixture-only demo controls, integration
tests, Make targets, locked exporter dependency and user/development guides.
No new source or runtime configuration is implemented by this proposal.

Status: proposed for user review on 6 October 2026. Implementation is pending.

## Planning Validation

On 6 October 2026, `make spec-check` passed all five current OpenSpec items,
including this proposal. Local Markdown links, balanced code fences and
whitespace in the five new documents were checked. No existing tracked files or
the secondary checkout were edited. No service was started and no dependency
was installed. `make check` and runtime/integration tests were not run for this
documentation-only task; none of the proposed runtime outcomes is verified.

## Publication Validation

Later on 6 October 2026, local `main` was synchronized with remote `main` at
`8bf1669a68a9072326d35abfb18ee979a3766531`, preserving the new proposal and backing
up the older local Review Capacity drafts. Before publication, `make check`
passed: lint, formatting, 83 tests and Compose configuration validation; five
opt-in container tests were skipped. `make spec-check` passed all five items.
Local links, code fences and whitespace were checked. The unrelated secondary
checkout remains untouched. No experiment service was started and no proposed
runtime outcome is verified by these checks. Implementation remains pending.
