# Bootstrap governed playground tasks

## Workflow and checkpoint

- [ ] Add the LangGraph workflow with Researcher, Builder, and Reviewer
  `create_agent` specialists and role-specific agent configuration files.
- [ ] Persist workflow checkpoints under ignored `.lab/` and pause after review
  for approve/reject against the exact artifact digest.

## Gateway and worker lifecycle

- [ ] Implement opaque expiring per-task grants, hashed token storage, role and
  capability allowlists, and gateway checks on each model/tool call.
- [ ] Record actor, role, run/task, event, outcome, and fixture provenance in
  the SQLAlchemy audit store; configure SQLite for local mode and Postgres for
  Compose.
- [ ] Add host CLI operations to launch fixed-template one-shot workers, revoke
  all grants for a run, and stop only that run's labelled workers.
- [ ] Define the Compose gateway, Postgres, and isolated worker network without
  Docker socket mounts or worker external egress.

## Stock-and-flow experiment

- [ ] Implement and document the deterministic backlog model, including its
  stocks, flows, units, boundary, assumptions, bounded inputs, and model
  version.
- [ ] Expose `system.describe`, `simulation.run`, and `simulation.review`
  through the gateway and reject invalid inputs before simulation.
- [ ] Build the local scripted-response fixture through the actual LangChain
  tool loop and label outputs and audit events as fixture-backed.
- [ ] Report hypothesis, variables, observations, and limitations without
  claiming real-world causal validity or live-provider quality or safety.

## Validation and user guidance

- [ ] Document the local demo, Compose target, fixture evidence limits, and
  container-runtime prerequisites in the user-facing README.
- [ ] Validate all OpenSpec artifacts and run the repository's canonical
  checks; report container execution as unavailable when no Docker daemon is
  present.
