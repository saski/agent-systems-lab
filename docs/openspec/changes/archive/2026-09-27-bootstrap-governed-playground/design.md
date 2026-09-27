# Design: governed playground bootstrap

## Runtime shape

Python 3.11+ is managed with `uv` and the committed lockfile. LangGraph owns the
macro workflow and checkpointed state. Each specialist is a LangChain
`create_agent` instance with a role-specific `agent.yaml`, `persona.md`, and
skills. The initial roles are Researcher, Builder, and Reviewer. These files
shape behavior only; the gateway's deterministic policy is the authority for
access.

The host CLI creates a run and launches one-shot workers from a fixed worker
template. Docker workers use an internal Compose network with no external
egress and can reach the gateway. Local process mode is trusted development
execution without filesystem or network sandboxing.
The gateway fronts all model requests and the three experiment tools:
`system.describe`, `simulation.run`, and `simulation.review`. It validates every
call using an opaque, expiring per-task grant and the calling role's allowlist.
Tokens are stored and compared as hashes. The host can revoke every grant in a
run and stop only workers carrying that run's labels. V0 does not let agents
create or delegate to child workers.

```text
Trusted host CLI / LangGraph
        | starts fixed, one-shot workers; retains checkpoints in .lab/
        v
Isolated workers: Researcher | Builder | Reviewer
        | model and tool calls with per-task grant
        v
Deterministic gateway ----> scripted fixture model
        |
        +----> system.describe / simulation.run / simulation.review
        +----> SQLAlchemy audit store: SQLite local demo, Postgres in Compose
```

## Trust and authorization

- The host CLI is trusted orchestration and owns worker lifecycle. It does not
  pass host credentials or the Docker socket to workers.
- The gateway is the only authorization point and owns provider credentials.
  It checks grant expiry, revocation, task identity, role, and tool/model
  allowlist on each call. A run-wide revocation invalidates all its task grants.
- Worker containers have no external egress. Agent prompts, skills, and model
  output cannot issue or expand grants.
- Audit events capture stable actor, role, task/run, event type, and outcome
  identities without storing bearer tokens. The local demo persists this state
  in SQLite; the Compose target uses Postgres.
- The fixed worker image/template and explicit host stop operation bound worker
  creation and cleanup. This does not claim a hardened general-purpose sandbox.

## Workflow and human decision

The workflow collects the question and experiment inputs, runs the three
specialists through LangChain's tool loop, and has the Reviewer produce a
review artifact with a content digest. LangGraph checkpoints before pausing for
a human decision. The human decision records approve or reject against that
exact digest; a mismatch cannot approve a changed artifact. The decision ends
the local workflow and does not trigger external publication.

For the local demo, scripted responses exercise the actual LangChain agent and
tool loop through a fixture model adapter. The demo requires no provider
credentials and makes no provider requests. Every result and audit record must
identify fixture provenance. This demonstrates workflow wiring and policy
enforcement only; it is not a live-provider evaluation. Live model routing may
be added later behind fixed gateway configuration, with credentials remaining
in the gateway.

## Experiment model

The first experiment is a deterministic stock-and-flow backlog model. Its
description names the system boundary, stocks, flows, assumptions, and units.
The gateway limits simulations to 1,000 steps and rejects non-finite computations.
An observation delay at least as long as the horizon means the controller
observes only the initial backlog throughout that finite experiment.
The run accepts bounded, validated inputs and records the hypothesis, variables,
and time horizon. The review reports observations and limitations, including
that deterministic fixture runs do not establish real-world causal validity.
The experiment exposes only `system.describe`, `simulation.run`, and
`simulation.review`; it does not expose arbitrary shell or code execution.

## Storage and deployment

LangGraph SQLite checkpoints and local run artifacts live under ignored
`.lab/`. The local gateway audit store uses SQLAlchemy with SQLite for a
credential-free demo. Docker Compose runs the gateway and Postgres plus
independent one-shot workers. Worker containers receive neither the Docker
socket nor external network access. The CLI is responsible for revoking grants
and stopping the exact run's labelled workers. A machine without a Docker
daemon can run the local demo but cannot demonstrate this container runtime;
CI should validate Compose and exercise containers when available.

## Deferred architecture

Fixed live-model routes, dynamic delegation with attenuated grants, OTLP
telemetry, stronger isolation, and general coding workflows remain future
directions. None is part of the first slice's delivered behavior or acceptance
claim.
