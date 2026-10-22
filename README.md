# Agent Systems Lab

We use this lab to study how work moves through an agent system, where it waits,
and who can decide what happens next. The experiments are small enough to rerun
and inspect. The numerical models draw on Donella Meadows's *Thinking in
Systems*; the agent workflow lets us study permissions and human intervention
in running code.

Each experiment starts with a question. We hold the setup steady, change one
factor and look at the result before adding more autonomy or infrastructure.
The learning goal is to explain why a result follows from the rules we chose,
and where that explanation stops being useful.

**Current state: 21 October 2026.** The workflow, permission checks, activity
dashboard, saved Review Capacity comparison, two numerical experiments and
fixture admission are implemented. All agent model responses are scripted
fixtures: predefined replies that let us repeat the same workflow without an
external model provider or model token costs. The workers and permission checks
still run. Numerical results describe the systems we modeled; they do not
measure agent or team productivity.

[![Activity dashboard: one task waiting for human review, verified history and a separate observation-delivery queue](docs/images/readme/activity-overview.jpg)](docs/dashboard.md)

*Captured on 16 October from a fresh local run of the three specialist processes.
The run is waiting for a human decision. Telemetry export is disabled, so its
32 recorded observations remain pending; that count is separate from task work.
[Capture context and source hashes](docs/images/readme/captures.json).*

## What we are exploring

- In the numerical models, we study stocks (work that has accumulated) and flows
  (work entering or leaving), then see what changes when information arrives
  late or one stage has less capacity than another. Review Capacity adds a
  limit on work in progress, or WIP: tasks admitted but not yet decided.
- In the agent workflow, we study how specialist roles work together, which
  actions they are allowed to take, and how the system pauses or recovers when
  a person needs to intervene.
- In the dashboard, we learn to read the evidence. An action being requested,
  authorized and completed are different observations. So are a task waiting
  for review and an event waiting to reach a telemetry collector.

Each experiment keeps its question, hypothesis, inputs, observations and
limitations together. A fixture run can demonstrate the workflow and its
controls under those conditions. It cannot establish the reasoning quality or
safety of a real model.

If you are starting here, run the workflow below and follow one task to human
review. Then use Backlog Feedback to study a single queue, and Review Capacity
to compare where work waits across several stages. Fixture admission takes the
WIP rule into the running workflow, where a human decision has to release it.

## Progress at a glance

| Area | Available now | Remaining work |
| --- | --- | --- |
| Governed workflow | Three specialists, checkpoint recovery, role-scoped access, budgets, revocation and approval tied to the exact artifacts; local processes and optional Docker workers | Live-model and alternative-runtime comparisons are future experiments |
| Backlog feedback | Deterministic model, controlled observation-delay comparison, scenario and documented results | Further sensitivity experiments with different gains, arrivals and capacity bounds |
| Review Capacity | Completed v0.2: A/B/C numerical comparison, local CLI, hashed exports, viewer-authorized report API, integrated charts and task replay, plus an offline learning guide | Variable workload, review quality and rework remain future experiments |
| Fixture admission | Two fixed tasks, WIP one per batch, saved run identities, one current coordinator, locks held by workers and decisions tied to the reviewed artifacts | Local POSIX processes and SQLite only; parallel/container admission and a batch dashboard remain outside this slice |
| Activity and history | Read-only Activity dashboard, task counts and wait ages, role tools, lifecycle events, session charts and saved-checkpoint comparison; separate saved-report Experiments view | Persistent historical charts |
| Telemetry delivery | Durable event journal, retry outbox, correlated OpenTelemetry spans and an optional local Collector | The Grafana/Tempo/Prometheus reliability learning lab is a documented proposal; implementation has not started |

## How the system works

The first workflow takes one backlog scenario through
**Researcher → Builder → Reviewer → human decision**. Each specialist runs in a
separate process, or an isolated one-shot container in Docker mode.

1. LangChain specialists run the model/tool loop: a model requests a tool,
   receives its result and continues. The Researcher describes
   the system, the Builder runs its simulation, and the Reviewer checks the
   output. Their personas and selected skills guide behavior.
2. LangGraph coordinates that fixed sequence, validates the result and saves
   checkpoints so the workflow can resume after a pause for human review.
3. The gateway checks every model and tool call against rules in code. It checks
   the caller's identity, the operations allowed for that role, permission
   expiry, call budgets and whether access has been revoked.
   Personas, skills and model output cannot grant permissions.

[![System map: operator, orchestrator, specialists, policy gateway, audit ledger and optional OTLP export](docs/images/readme/system-map.jpg)](docs/architecture.md)

*The map shows the configured components. Worker activity and completion come
from recorded lifecycle events; the topology alone does not prove process health.*

The gateway stores the outputs, called artifacts, and keeps an append-only
event journal. Each event includes a hash that links it to the previous one, so
we can check whether the recorded history still agrees with those links. SQLite stores
local operational state; Compose uses Postgres. LangGraph keeps its checkpoints
separately.

Human approval must match a digest, a hash of the scenario, artifacts and policy
version. This ties the decision to the material the person reviewed. Acceptance
records that decision and resumes the workflow; it does not publish, merge or
deploy anything.

## Run it locally

Requirements: [uv](https://docs.astral.sh/uv/), Python 3.11+, and Make.
From the repository root:

```sh
make setup
make dashboard
# In another terminal:
make dashboard-demo
```

Open <http://127.0.0.1:8765/dashboard> and connect with `.lab/viewer.token`.
The viewer is read-only. Select **Experiments** to inspect saved Review Capacity
reports alongside Activity. Create a report first with `make review-capacity-demo`,
then select **Refresh reports**. Runs, credentials, checkpoints and generated
artifacts stay under ignored `.lab/`.

The demo prints a run ID, artifact directory, digest and the next command.
Inspect the JSON artifacts before recording your decision in the operator
terminal:

```sh
uv run --locked systems-lab --gateway http://127.0.0.1:8765 status RUN_ID
uv run --locked systems-lab --gateway http://127.0.0.1:8765 decide RUN_ID --digest DIGEST --approve
# Or: replace --approve with --reject
```

For a terminal-only run, `make demo` starts and stops a temporary local gateway.
Use its printed next command for the decision. Local process mode is **not an
OS sandbox**; the optional container mode below exercises filesystem and
network boundaries.

## Experiments and observations

### 1. Governed execution and human intervention

Here we want to learn whether three specialists can complete a bounded workflow,
pause for a decision on the exact artifacts they produced, and recover without
bypassing authorization.

The fixture workflow is runnable end to end. Tests cover role denials, grant
limits, revocation, checkpoint recovery and digest-bound decisions. The opt-in
container suite additionally exercises worker network/database exclusion and
stopping a run's labelled container.

<details>
<summary>Screenshot: the specialist workflow has reached human review</summary>

![Selected fixture run with completed specialist stages and a pending human-review checkpoint](docs/images/readme/run-inspector.jpg)

</details>

The useful observation is where the workflow stops, and which checks still
apply when it resumes. The tests establish behavior with these fixtures and
trust assumptions. The host and gateway are trusted; local processes have no
filesystem confinement, and Docker mode is not a security platform for mutually
untrusted users.
See [architecture and trust boundaries](docs/architecture.md).

### 2. Backlog feedback: reacting to delayed information

Here we study a controller that adjusts processing capacity using the backlog
it can see. If that observation is old, its next adjustment responds to a state
the system has already left behind.

The model has one backlog, constant arrivals, bounded processing capacity and
a backlog-based controller. Holding the supplied 36-step scenario constant and
changing only observation delay gives:

| Observation delay | Peak backlog | Completed tasks | Total capacity movement |
| ---: | ---: | ---: | ---: |
| 0 steps | 10.00 | 362.00 | 7.60 |
| 4 steps | 12.76 | 359.87 | 16.81 |

With a four-step delay, this controller moves capacity more, reaches a higher
backlog peak and completes slightly less work. Follow the backlog and capacity
together to understand the response. These results depend on the chosen
parameters; the model is not calibrated for staffing decisions, and this run
does not establish a universal effect of delay.

`make dashboard-demo` runs this scenario through the specialist workflow and
exports `simulation.json`. The [backlog feedback guide](experiments/backlog-feedback/README.md)
defines the update order, assumptions and observations; the
[experiment guide](experiments/README.md) explains how to compare another delay.

### 3. Review Capacity: faster execution, fixed review capacity

This experiment follows work all the way to a decision. We want to learn what
extra execution capacity changes when the capacity to review its output stays
fixed. Counting only finished execution would miss the work still waiting for
review.

The model follows 24 tasks through admission, execution and one synthetic
reviewer. It compares one execution slot, four slots, and four slots with an
admitted-WIP limit of three. At the common horizon of **logical tick 60**:

| Policy | Decisions completed | Waiting for review | Waiting for admission | All unfinished tasks |
| --- | ---: | ---: | ---: | ---: |
| A: 1 execution slot | 6 | 0 | 16 | 18 |
| B: 4 execution slots | 8 | 15 | 0 | 16 |
| C: 4 slots, WIP limit 3 | 8 | 1 | 13 | 16 |

All unfinished tasks also include work currently executing or being reviewed.
Four execution slots yield 8 decisions versus 6 at this horizon. The WIP limit
reduces the review queue but moves waiting upstream: B and C finish the same
number of decisions and both drain all 24 tasks by tick 152; A drains by tick 198.

[![Synthetic Review Capacity comparison: decisions and all unfinished work at tick 60](docs/graphics/review-capacity/comparison.png)](experiments/review-capacity/README.md)

Reproduce the comparison without launching agents or making gateway calls:

```sh
make review-capacity-demo
```

Each attempt creates a new directory under `.lab/experiments/review-capacity/`
with its scenario, report and integrity manifest. The
[illustrated experiment guide](experiments/review-capacity/README.md) explains
the queues, full-drain curves and limitations. Download and open the
[standalone HTML learning guide](docs/graphics/review-capacity/explainer.html)
locally to replay task states without a server.

The dashboard's separate **Experiments** view compares saved, complete,
hash-verified reports at a common observation horizon. It shows decision and
unfinished-work counts, queue sizes, latency percentiles with sample counts,
full-drain status and step charts. Select a policy to replay task positions at
any logical tick, or use Play/Pause and the 0.5×, 1×, 2× or 4× viewing speeds.
This is a local replay of saved data: it does not launch agents, run a new
simulation in the browser or record operational decisions. Logical ticks are
not seconds. The model uses uniform service times and a reviewer that accepts
every task; it measures neither real agent concurrency nor human review quality,
cost or productivity. The offline interactive guide remains available as a
complementary way to study the model without the dashboard.

### 4. Fixture admission: keeping a place occupied until a decision

The [fixture-workflow admission experiment](experiments/fixture-workflow-admission/README.md)
applies a WIP limit to the running workflow. It queues two fixed tasks and admits
one at a time. When the first reaches human review, it keeps its place; the
second stays queued. The learning goal is to follow that boundary through a
pause, a restart and an explicit decision, without accidentally starting the
same work twice.

Start with `make fixture-admission-create`, then advance the returned batch
explicitly. Its local state is isolated under `.lab/fixture-admission`.
Decisions remain explicit operator actions. The guide explains how saved run
identities, ownership checks and process locks support this behavior, and why
uncertain worker state blocks further admission. This experiment supports local
POSIX processes and SQLite, with a WIP limit per batch.

## Read activity and verify evidence

The **Activity** view distinguishes work in the workflow, work waiting for your
review, finished decisions and revoked access. It shows wait ages, tools
available to each role, recorded actions, and operator CLI commands. Two
separate charts track task state and observation delivery during the current
browser session; they reset on reload. The **Experiments** view presents the
saved Review Capacity model separately from live activity.

History verification and telemetry delivery are independent signals. A saved
checkpoint can be compared with the current journal, including after later
events. Keep an independent copy to detect rewriting against that earlier
history; a privileged database owner can rewrite the local chain.

OpenTelemetry export is disabled by default. When explicitly enabled, a stored
delivery queue, the outbox, retries sending events and preserves stable
trace/span IDs. Delivery is at least once: the receiver may get an event again
after a retry. Prompts, credentials, tool arguments, response bodies and scenario
contents are excluded. The optional Collector is already available; the Grafana
learning lab remains a proposal.

See the [illustrated dashboard tour](docs/dashboard.md) and
[activity, telemetry and history guide](docs/observability.md) for checkpoint
commands, Collector setup and the limits of each signal.

## Optional container mode

Requirements: Docker Engine and Docker Compose v2.24+ (including v5).

```sh
make containers-up
make containers-demo
```

Each specialist runs in a temporary container with no external network egress,
host mounts or Docker socket, a read-only root filesystem and resource limits.
The gateway and Postgres stay running. Open the same dashboard URL and use that
gateway for decisions or interventions:

```sh
uv run --locked systems-lab --gateway http://127.0.0.1:8765 revoke RUN_ID --stop-containers
make containers-down
```

Stopping Compose retains its database volume. Local SQLite and Compose/Postgres
are independent histories; use the gateway corresponding to the run.

## Next experiments and further reading

Review Capacity v0.2 is [verified and closed](docs/openspec/changes/archive/2026-10-20-review-capacity-experiment/verification.md).
The proposed [telemetry reliability
learning lab](docs/plans/2026-10-06-agent-telemetry-reliability-lab.md) asks how to
diagnose delivery failures using traces in Grafana/Tempo and metrics that remain
available when the Collector stops. A separate [Dafny call-budget
experiment](docs/openspec/changes/dafny-call-budget/proposal.md) asks what a formal
proof could establish about a call limit beyond the cases covered by tests.
Neither proposal is implemented. [OpenSpec](docs/openspec/changes/) keeps their
scope and acceptance criteria.

The [evolution roadmap](docs/roadmap.md) also explores fixed live-model routes,
runtime substitution, constrained child delegation and sandboxed coding. Live
models, dynamic delegation, arbitrary code execution, web research and external
writes are not enabled in the current specialist workflow.

- [Experiment design and reading notes](experiments/README.md)
- [Development, validation and screenshot provenance](docs/development.md)
- [OpenSpec requirements](docs/openspec/)
- [When human review becomes the bottleneck — the experiment and its limits](https://www.saski.com/notes/agent-systems-lab/)
- [More Notes on saski.com](https://www.saski.com/notes/)
