# Governed execution

## ADDED Requirements

### Requirement: gateway authorization on every call

The system SHALL route every specialist model request and tool invocation
through a deterministic gateway that checks the current task's grant, expiry,
revocation state, role, and allowlist before dispatch.

#### Scenario: allowed call uses an active role grant

- GIVEN a task has an unexpired grant for the Researcher role
- AND the requested model route or tool is in that role's allowlist
- WHEN the specialist makes the request through the gateway
- THEN the gateway dispatches it and records the authorization outcome

#### Scenario: disallowed or expired call is blocked

- GIVEN a task grant is expired, revoked, or does not allow the calling role or
  requested capability
- WHEN a specialist makes that model or tool call
- THEN the gateway rejects the call before dispatch
- AND records the denied outcome without storing the bearer token

### Requirement: opaque expiring task grants

The system SHALL issue opaque, expiring per-task grants, store only token
hashes, and bind each grant to its run, task, role, and allowlist. Specialist
configuration, prompts, model output, and skills SHALL NOT grant or expand
permissions.

#### Scenario: grant is bound to task and role

- GIVEN a run has separate Researcher and Builder tasks
- WHEN each task receives its grant
- THEN each grant authorizes only its assigned task and role capabilities
- AND a token hash rather than the bearer token is retained in the audit store

### Requirement: run-wide revocation and bounded worker lifecycle

The trusted host CLI SHALL be able to revoke all grants for one run and stop
only one-shot Docker workers labelled with that run. Docker workers SHALL be
created from a fixed template, have no Docker socket mount, and have no external
network egress. Local process mode SHALL be explicitly documented as trusted,
without OS sandboxing or a process kill guarantee. V0 SHALL NOT support dynamic
child-agent delegation.

#### Scenario: revocation stops subsequent authorized work

- GIVEN a run has multiple active task grants and Docker workers
- WHEN the host CLI revokes that run
- THEN every later model or tool call for those grants is rejected
- AND the CLI can stop workers carrying that run's labels without stopping
  workers from another run

### Requirement: auditable identities and fixture provenance

The system SHALL record actor, role, run/task, event type, and outcome for
authorization and workflow events. The local demo SHALL use scripted model
responses through the actual LangChain `create_agent` tool loop, require no
provider credentials, make no provider requests, and label fixture-backed
outputs and audit records with fixture provenance. Fixture results SHALL NOT
be represented as live-provider quality or safety evidence.

#### Scenario: local fixture run leaves attributable evidence

- GIVEN the local demo is configured for scripted responses
- WHEN the Researcher, Builder, and Reviewer complete their workflow
- THEN each model/tool event is attributable to its actor, role, and run
- AND generated results identify fixture provenance
- AND no provider credentials or provider requests are required
- AND no result claims that a live provider passed an evaluation

### Requirement: checkpointed human review

The workflow SHALL persist LangGraph SQLite checkpoints under ignored `.lab/`
and interrupt after review for a human decision. An approval or rejection
SHALL refer to the exact reviewed artifact digest and SHALL NOT publish
externally.

#### Scenario: review waits for a decision on the same digest

- GIVEN the Reviewer has produced an artifact with digest D
- WHEN the workflow reaches its review interrupt
- THEN it persists a checkpoint and waits for a human decision
- AND a decision for digest D is recorded against D
- AND a decision for another digest cannot approve the artifact
- AND neither decision causes external publication

### Requirement: local and container audit stores

The gateway SHALL use SQLAlchemy-backed SQLite for the credential-free local
demo and Postgres for the Docker Compose target.

#### Scenario: local audit state uses SQLite

- GIVEN the gateway starts in local demo mode
- WHEN it persists grants and audit events
- THEN it uses the configured local SQLite database

#### Scenario: Compose audit state uses Postgres

- GIVEN the gateway starts in the Compose runtime
- WHEN it persists grants and audit events
- THEN it uses the configured Postgres database
