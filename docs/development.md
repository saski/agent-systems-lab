# Development

## Setup and checks

```sh
make setup
make check
make spec-check
```

`make check` runs Ruff lint/format checks, pytest, and Compose configuration
validation. Three container integration tests are skipped unless explicitly
enabled. `make spec-check` requires the OpenSpec CLI; the bootstrap used 1.10.0.

`make format` applies Ruff formatting and safe lint fixes. Python dependencies
are locked in `uv.lock`; use `uv add` for deliberate changes and commit the lockfile.

## Container verification

```sh
make containers-up
LAB_CONTAINER_TESTS=1 uv run --locked pytest tests/test_containers.py
make containers-down
```

The container suite exercises the full workflow against Postgres, verifies
worker external-network and database exclusion, and revokes a run while stopping
its labelled container. GitHub Actions runs this suite on a Linux Docker host.
An absent local Docker daemon is an unavailable check, not a successful one.

The Compose database uses a clearly marked local-development password and is
not published to the host. The operator credential is generated in ignored
`.lab/` with restrictive permissions and passed only to the gateway. Do not
reuse this configuration for a public or multi-user deployment.

## Repository map

```text
agents/                 # Specialist identity, persona, selected skills
src/systems_lab/
  cli.py                # Operator entrypoint and local gateway lifecycle
  orchestrator.py       # LangGraph and fixed worker launcher
  runtime.py            # LangChain adapter and AgentResult contract
  worker.py             # One-shot stdin/stdout process
  gateway.py            # Authenticated API, tools, scripted model route
  store.py              # Deterministic policy, grants, audit, artifacts
  simulation.py         # Pure stock-and-flow model
experiments/            # Scenarios, hypotheses, interpretation and reading notes
tests/                  # Numerical, authorization, workflow and container checks
docs/openspec/          # Current requirements and reviewable changes
```

## Add an experiment

Start with the experiment guide and one behavior-level test. Keep deterministic
model calculations independent of the agent framework. Extend the gateway with
a typed, resource-bounded operation, then explicitly grant it to the needed
role. Unknown operations must remain denied.

Add a real model only through an explicit gateway route change and evaluation.
Do not inject provider keys into workers or claim fixture results establish
model quality. Do not add an unrestricted URL proxy or shell to simplify an integration.

## OpenSpec

`openspec` at the root is a symlink to `docs/openspec/`. Use the shared OpenSpec
workflow to propose, implement, verify, and archive meaningful changes:

```sh
openspec list
openspec list --specs
openspec validate --all --strict
```

Keep requirements focused on the current experiment. The roadmap is not a
promise that all proposed capabilities are already implemented.

## Local state

`.lab/control.db` stores local operational evidence; `.lab/checkpoints.db`
stores workflow checkpoints; `.lab/runs/<run-id>/` contains JSON exports.
The Compose operational store lives in its named Postgres volume. Operator
credentials, databases, and artifacts stay out of Git and Docker build context.

V0 has no database migration framework. Schema changes require an explicit
state migration or a new laboratory data directory; never silently delete
existing experiment evidence to accommodate a code update.
