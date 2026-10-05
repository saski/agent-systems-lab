## ADDED Requirements

### Requirement: bounded deterministic review-capacity model

The system SHALL provide a versioned pure event-time experiment with a finite
arrival list, bounded parallel execution slots, one synthetic reviewer, FIFO
ordering and strictly positive service durations. It SHALL validate bounded
inputs before executing and resolve simultaneous events deterministically.

#### Scenario: repeat the same finite workload

- GIVEN the same validated inputs and model version
- WHEN the experiment runs twice
- THEN deterministic report bytes and report hashes are identical
- AND no wall-clock sleep, provider request or agent workflow is needed

#### Scenario: invalid or unbounded input

- GIVEN a scenario with unknown fields, invalid capacities or out-of-bound times
- WHEN the experiment is requested
- THEN it fails validation before computation or result publication

### Requirement: controlled policy comparison

The initial experiment SHALL compare one execution slot, four execution slots,
and four execution slots with total WIP capped at three. All cases SHALL use the
same arrivals, task service demand, review service, ordering and horizons.

#### Scenario: compare execution capacity and admission policy

- GIVEN the recorded 24-task scenario
- WHEN policies A, B and C are evaluated
- THEN A and B differ only in execution slots
- AND B and C differ only in the WIP admission limit
- AND each report includes complete inputs and explicit synthetic provenance

### Requirement: total-WIP admission and visible upstream queue

Admitted WIP SHALL include execution, awaiting review and review service until
the simulated decision. Admission SHALL require both a free execution slot and
available WIP capacity. Work waiting before admission SHALL remain visible.

#### Scenario: execution completes while review capacity is occupied

- GIVEN policy C has three admitted unfinished tasks
- WHEN one task completes execution and waits for review
- THEN no WIP slot is released
- AND a fourth task remains queued upstream until a simulated decision

### Requirement: trace-reconciled metrics and incomplete work

The experiment SHALL record per-task lifecycle ticks and derive admission wait,
review wait, end-to-end time, queue occupancy, accepted output, reviewer use and
drain makespan from the trace. Fixed-window metrics SHALL include unfinished
counts and sample sizes. Conservation and configured capacity bounds SHALL hold
at every recorded state.

#### Scenario: the observation horizon ends before all decisions

- GIVEN tasks are still queued or in service at tick 60
- WHEN the fixed-window summary is generated
- THEN those tasks are reported as unfinished with current states
- AND completed-task latency is identified as a censored subset
- AND a separate bounded full-drain result covers all tasks or reports incompletion

### Requirement: separate synthetic evidence and preserved attempts

The system SHALL export synthetic traces separately from actual worker and
operator history. It SHALL label reports `synthetic_event_time_model`, use
`simulated_decision` for modeled decisions and create fresh attempt directories
without overwriting earlier results. It SHALL NOT represent report hashes as an
immutable-storage guarantee or emit simulated transitions as workflow OTLP spans.

#### Scenario: rerun a recorded scenario

- GIVEN an existing complete report attempt
- WHEN the same scenario is run again
- THEN a new attempt retains the same deterministic report hash
- AND the original attempt remains unchanged
- AND no `Store.decide`, worker lifecycle or canonical `run.decision` is emitted

### Requirement: authenticated bounded read-only report access

The local dashboard SHALL read complete hash-checked experiment attempts through
viewer-authenticated GET endpoints with validated IDs and bounded content. It
SHALL NOT accept arbitrary caller-provided filesystem paths or executable content.

#### Scenario: request an incomplete or altered report

- GIVEN an attempt is incomplete, oversized or fails its stored content hashes
- WHEN the viewer requests it
- THEN the gateway returns a clear error rather than a verified result

### Requirement: clearly labeled experiment playback

The dashboard SHALL provide a policy comparison, queue and decision charts, and
logical-tick flow replay with visible simulation provenance. Replay controls
SHALL only manipulate local presentation, honor reduced motion and stay separate
from live run counts, journal integrity and operational health indicators.

#### Scenario: seek through a recorded experiment

- GIVEN a loaded synthetic report
- WHEN the viewer plays, pauses or seeks its timeline
- THEN the view displays states from that report with a SIMULATION REPLAY label
- AND no worker is launched, decision recorded or report changed
- AND existing live Activity behavior remains independent

### Requirement: evidence-bounded interpretation

The experiment guide SHALL state the question, predicted behavior, system
boundary, inputs, observed results and limitations. It SHALL distinguish
synthetic operator capacity, actual fixture-workflow evidence and live-model
quality, and SHALL report contradictory observations rather than enforcing the
hypothesis as a general conclusion.

#### Scenario: publish findings from the initial scenario

- GIVEN an implemented model produced a reconciled report
- WHEN its findings are documented
- THEN claims refer to the recorded scenario and its observed metrics
- AND waiting before admission and incomplete work are accounted for
- AND no conclusion claims measured human-review quality or live-model safety
