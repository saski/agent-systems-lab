# Agent Telemetry Reliability Lab

## Why

A quiet activity screen can mean slow or failed execution, a legitimate human
review checkpoint, or interrupted telemetry. The lab already has canonical
history and recoverable OTLP trace delivery, but lacks a queryable trace backend
and independent metrics for learning how to distinguish those conditions.

The primary outcome is learner understanding through a real fixture workflow,
queries and controlled failures. The [learning plan](../../../plans/2026-10-06-agent-telemetry-reliability-lab.md)
explains the baseline, options, exercises, sources, estimates and demonstration.

## What Changes

- Add an opt-in local LGTM backend, using the existing lab Collector as an
  independently stoppable ingestion hop, with traces stored in Tempo.
- Add five read-only OTel metric families, scraped directly by Prometheus, plus
  direct Collector self-metric collection outside its own delivery pipeline.
- Provision a compact Grafana dashboard and one local alert rule with explicit
  missing/stale/error behavior.
- Add bounded fixture delay/failure exercises and a read-only comparison of a
  finite run's expected journal spans against queryable Tempo evidence.
- Supply a startup guide, learner exercises, three-minute demo and limitations.

## Acceptance Scope

Fresh fixture runs, one gateway/exporter per database, normal execution,
human-review pending, short worker delay/failure, a stopped ingress Collector,
recovery and retransmission, and explicit missing-data evidence. Recovery must
preserve canonical history and event identities. Accepted-but-missing downstream
evidence must be detectable by finite comparison, without claiming permanent
retention or automatic replay after acknowledgement.

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
