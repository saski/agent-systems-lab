# Bootstrap a governed systems-thinking playground

## Why

The lab needs a small runnable experiment that makes agent permissions and
system behavior observable. The first slice uses a stock-and-flow backlog model
while reading Donella Meadows' *Thinking in Systems*. It establishes a governed
workflow that can later support other experiments without implying that the
initial system is a general-purpose coding agent.

## What changes

- Define a Python/uv runtime with a LangGraph macro workflow and LangChain
  `create_agent` specialists: Researcher, Builder, and Reviewer.
- Put deterministic authorization and model/tool proxying in a gateway outside
  the specialists. Give each task opaque, expiring grants and enforce them on
  every call.
- Provide the bounded tools `system.describe`, `simulation.run`, and
  `simulation.review` for a deterministic stock-and-flow backlog experiment.
- Run scripted responses through the real LangChain tool loop in the local
  fixture mode, and label the resulting evidence as fixture-backed.
- Persist gateway audit state locally with SQLAlchemy/SQLite and in the Compose
  target with Postgres. Persist LangGraph checkpoints under ignored `.lab/` and
  interrupt for human review of an exact digest.
- Let the trusted host CLI start one-shot workers from a fixed template, revoke
  all grants for a run, and stop workers labelled for that run.

## Non-goals

- Arbitrary coding tasks, production use, or claims of real-provider quality or
  safety.
- Provider credentials in workers, Docker socket mounts, or worker egress to the
  external network.
- Dynamic child-agent delegation, live-model routing, OTLP telemetry, or a
  general-purpose sandbox.
- External publication or side effects after human review.

## Acceptance

- A local demo completes the experiment through the actual LangChain tool loop
  using scripted responses, needs no provider credentials or provider requests,
  and identifies fixture provenance in its output and audit trail.
- Each model or tool call is authorized by the gateway against the current
  task's role allowlist and unexpired grant; revocation blocks later calls for
  the whole run.
- The run records auditable actor, role, run, and event identities, and the
  workflow pauses after review until a human approves or rejects the exact
  reviewed digest.
- The stock-and-flow experiment reports its hypothesis, system boundary,
  variables, observations, and limitations.
- The Compose configuration describes a gateway/Postgres service pair and
  isolated one-shot workers without a Docker socket or external egress. Actual
  local container execution may be unavailable where no Docker daemon exists;
  container behavior is a target for CI validation.

## Roadmap after this slice

Live models through fixed gateway route configuration, attenuated dynamic
delegation, OTLP telemetry, stronger sandboxing, and general coding workflows
are future work and are not acceptance criteria for this change.
