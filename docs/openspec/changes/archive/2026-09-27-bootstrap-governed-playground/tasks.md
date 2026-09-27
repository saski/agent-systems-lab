# Bootstrap governed playground tasks

## Workflow and checkpoint

- [x] Add the LangGraph workflow with Researcher, Builder, and Reviewer
  `create_agent` specialists and role-specific agent configuration files.
- [x] Persist workflow checkpoints under ignored `.lab/` and pause after review
  for approve/reject against the exact artifact digest.

## Gateway and worker lifecycle

- [x] Implement opaque expiring per-task grants, hashed token storage, role and
  capability allowlists, and gateway checks on each model/tool call.
- [x] Record actor, role, run/task, event, outcome, and fixture provenance in
  the SQLAlchemy audit store; configure SQLite for local mode and Postgres for
  Compose.
- [x] Add host CLI operations to launch fixed-template one-shot workers, revoke
  all grants for a run, and stop only that run's labelled workers.
- [x] Define the Compose gateway, Postgres, and isolated worker network without
  Docker socket mounts or worker external egress.

## Stock-and-flow experiment

- [x] Implement and document the deterministic backlog model, including its
  stocks, flows, units, boundary, assumptions, bounded inputs, and model
  version.
- [x] Expose `system.describe`, `simulation.run`, and `simulation.review`
  through the gateway and reject invalid inputs before simulation.
- [x] Build the local scripted-response fixture through the actual LangChain
  tool loop and label outputs and audit events as fixture-backed.
- [x] Report hypothesis, variables, observations, and limitations without
  claiming real-world causal validity or live-provider quality or safety.

## Validation and user guidance

- [x] Document the local demo, Compose target, fixture evidence limits, and
  container-runtime prerequisites in the user-facing README.
- [x] Validate all OpenSpec artifacts and run the repository's canonical
  checks; report container execution as unavailable when no Docker daemon is
  present.
