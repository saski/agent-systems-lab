# Systems experiments

## ADDED Requirements

### Requirement: bounded stock-and-flow experiment

The system SHALL provide a deterministic stock-and-flow backlog experiment
with explicit stocks, flows, units, assumptions, and system boundary. The
first slice SHALL use this experiment as its vertical slice and SHALL NOT
accept arbitrary coding tasks or execute arbitrary code.

#### Scenario: describe the system before running it

- GIVEN a run requests the backlog experiment
- WHEN the Researcher calls `system.describe`
- THEN the tool returns the model boundary, stocks, flows, units, and
  assumptions
- AND those details are available to the Reviewer

### Requirement: reproducible validated simulation

The system SHALL expose `simulation.run` as a bounded deterministic operation
with validated inputs and a fixed model definition/version. It SHALL record
the hypothesis, independent and controlled variables, and time horizon with
the run so that repeated inputs produce the same observations.

#### Scenario: run the same bounded inputs twice

- GIVEN two runs use the same model version and validated inputs
- WHEN `simulation.run` executes both runs
- THEN both runs produce the same time-series observations
- AND each run records the hypothesis, variables, and time horizon

#### Scenario: reject invalid inputs before simulation

- GIVEN requested parameters fall outside the experiment's documented bounds
- WHEN a specialist calls `simulation.run`
- THEN the tool rejects the request with a validation outcome
- AND it records no successful simulation result for that request

### Requirement: explicit experiment review and evidence limits

The system SHALL expose `simulation.review` to summarize results against the
hypothesis and report observations, limitations, and fixture provenance when
the run used scripted model responses. Review output SHALL distinguish
observations produced by the model from conclusions that the experiment does
not establish.

#### Scenario: review fixture-backed observations

- GIVEN a deterministic backlog run completed through scripted model
  responses in the actual LangChain tool loop
- WHEN the Reviewer calls `simulation.review`
- THEN the review states the hypothesis, boundary, variables, and observed
  changes in stocks and flows
- AND identifies the output as fixture-backed
- AND states that deterministic observations do not establish real-world
  causal validity or live-provider quality and safety

### Requirement: narrow experiment tool surface

The initial experiment SHALL expose exactly the bounded tools
`system.describe`, `simulation.run`, and `simulation.review` to specialist
workers through the gateway. It SHALL NOT expose shell execution, arbitrary
file writes, or general-purpose code execution.

#### Scenario: worker requests an unrelated capability

- GIVEN a specialist has a grant for the experiment tools
- WHEN it requests an unrelated shell, file-write, or code-execution tool
- THEN the gateway denies the request before dispatch
- AND records the denial in the run audit trail
