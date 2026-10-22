# Review capacity: where does the waiting go?

**Four execution slots complete 8 decisions by tick 60, compared with 6 using
one slot. A work-in-progress (WIP) limit of 3 keeps the same 8 decisions while
moving most waiting from review to admission.** These results come from the
supplied deterministic model. They do not measure agents or a real team's
productivity.

[Open the interactive learning guide](../../docs/graphics/review-capacity/explainer.html)
in a browser from a local checkout. It contains policy selection, a logical-time
slider and task replay. GitHub displays HTML as source; the figures below remain
readable there. The same learning is available in the dashboard's separate
**Experiments** view, which reads saved reports from the local gateway. The
standalone page complements that view with an offline replay.

## Start with the boundary

![Two numbered queues and the admitted-WIP boundary](../../docs/graphics/review-capacity/flow.svg)

The model has **two in-memory queues**. A task can enter execution only when a
slot is free and there is room under the work-in-progress (WIP) cap. Admitted
WIP includes tasks in execution, waiting for review or being reviewed. Tasks
waiting for admission sit outside the cap, but still count in the reported
workload. Finishing execution frees a slot; a simulated decision frees the
task's WIP place.

The synthetic reviewer is one modeled resource, separate from the playground's
Reviewer agent. An execution tick is one unit of logical model time for
abstract automated service. It does not time the Researcher, Builder or
Reviewer implementations.

## Question, prediction and controlled comparison

**Question:** when execution speeds up but review stays fixed, how many more
decisions does the system complete, and where does unfinished work accumulate?

**Prediction:** increasing execution slots will increase review waiting without
multiplying accepted output fourfold. A WIP cap may keep the reviewer supplied
while reducing admitted work and moving waiting upstream.

The checked-in [scenario](scenario.json) keeps these inputs fixed across the
three policies:

| Input | Value |
| --- | --- |
| Workload | 24 tasks, arriving at ticks 0, 2, …, 46 |
| Execution demand | 8 ticks per task |
| Review service | 6 ticks, one reviewer, every decision accepts |
| Scheduling | FIFO admission; review ordered by ready tick and task ID |
| Common observation | Tick 60, including transitions at that tick |
| Drain bound | Tick 500; actual final decision recorded separately |
| Model version | `review-capacity-v1` |

| Policy | Execution slots | Total admitted WIP cap |
| --- | ---: | ---: |
| A · baseline | 1 | None |
| B · more execution | 4 | None |
| C · bounded WIP | 4 | 3 |

FIFO means first-in, first-out: tasks enter admission in arrival order.
**A → B changes the number of execution slots. B → C changes only the admission
cap.** Ticks count logical model time, not seconds. At each tick, the model
completes services, registers arrivals, starts reviews and admits eligible
tasks to execution, then records the resulting state.

## Read delivery and unfinished work together

![Decisions and every pending task by location at tick 60](../../docs/graphics/review-capacity/comparison.svg)

| At tick 60 | A | B | C |
| --- | ---: | ---: | ---: |
| Simulated decisions completed | 6 | 8 | 8 |
| Total unfinished tasks | 18 | 16 | 16 |
| Waiting for admission | 16 | 0 | 13 |
| Executing | 1 | 0 | 1 |
| Waiting for review | 0 | 15 | 1 |
| Being reviewed | 1 | 1 | 1 |
| Admitted WIP | 2 | 16 | 3 |
| Not yet arrived | 0 | 0 | 0 |

Compare the policies in two steps:

1. **A → B:** 4× as many execution slots produce 8/6 = **1.33× as many
   completed decisions** in the same window. More execution increases output,
   while the fixed review service limits further increase. This ratio includes
   startup and finite-horizon effects, so it does not predict scaling in other
   workloads.
2. **B → C:** the review queue falls from **15 to 1**, while admission waiting
   rises from **0 to 13**. Total unfinished work remains **16**. The cap changes
   where tasks wait; it does not remove demand or create review capacity.

You can account for every task from the report:
`24 = admission queue + executing + review queue + reviewing + decided`.
At earlier ticks, also count tasks scheduled to arrive in the future.

## Follow the complete workload

![Decisions, both queues and admitted WIP through full drain](../../docs/graphics/review-capacity/trajectories.svg)

The dotted vertical line marks the common observation horizon. The curves
continue until all tasks finish, and each value holds between events. **B and C
complete each task at the same tick** in this scenario, even though their queues
contain very different numbers of tasks.

The makespan is the tick when the final task receives its decision. Here, the
full-drain latency and wait results use percentiles: p50 is the median, and p95
is the 95th percentile.

| Full drain · the same 24 tasks | A | B | C |
| --- | ---: | ---: | ---: |
| Final decision / makespan, ticks | 198 | 152 | 152 |
| End-to-end time p50 / p95, ticks | 80 / 146 | 58 / 102 | 58 / 102 |
| Admission wait p50 / p95, ticks | 66 / 132 | 0 / 0 | 40 / 84 |
| Review-queue wait p50 / p95, ticks | 0 / 0 | 44 / 88 | 4 / 4 |

The results support the prediction for this scenario: C keeps the reviewer
supplied while limiting how many tasks have been admitted. It also shows
the tradeoff: **delivery can happen at the same times even when the review queue
is smaller and more tasks wait for admission**. A WIP cap of 3 is sufficient
here. The experiment does not establish the right cap for other workloads or
measure cost, context switching or quality improvements.

## Read each metric with its sample size

- Horizon counts use decisions at or before tick 60. Pending means **all 24
  scheduled tasks minus those decisions**, including future arrivals when any
  remain. `not_arrived` identifies that portion separately.
- Horizon latency and wait percentiles include only tasks decided by that
  horizon: A has **n = 6**, while B and C have **n = 8**. These are completed
  subsets of the workload, and the policies do not necessarily decide the same
  tasks by tick 60.
- Full-drain percentiles use the same **n = 24** tasks for every policy. If the
  drain bound expires first, the report marks the run incomplete, leaves the
  makespan unavailable and retains the unfinished tasks.
- The model calculates percentiles with nearest rank: sort the values and
  select rank `ceil(p × n)`. When no task has completed,
  the percentile is `null`, not zero waiting.
- Queue means and utilization integrate post-transition occupancy over logical
  time. An unweighted average of event snapshots would bias the result.
  Execution utilization is normalized by execution slots.
- Admission wait is admission minus arrival; review wait excludes review
  service. End-to-end time includes both waits and both services. **Do not add
  component percentiles as a general rule**: a sum of medians is not generally
  the median of the sum.

## Inspect tasks one tick at a time

![Opening screen of the standalone numerical learning guide](../../docs/graphics/review-capacity/learning-guide-desktop.jpg)

In the [interactive guide](../../docs/graphics/review-capacity/explainer.html),
the **saved trace** module lets you inspect the same evidence at task level:

1. Select **A, B or C** to switch policy without changing the workload.
2. Use **Start**, **Horizon** and **Full drain**, or seek with the logical-tick
   slider. Each tile shows where one task is at that tick.
3. Read the two queues alongside occupied execution slots, the single synthetic
   reviewer and decided tasks. The footer reconciles WIP, future arrivals and
   total unfinished work.
4. Use **Play / Pause** and playback speed to follow the saved transitions.
   Playback speed changes viewing time, not the model or its results.

This page has embedded data and figures, so its replay also works offline.
It does not invoke workers, run a new experiment or operate permissions.

## Connect the result to systems thinking

In systems thinking, a queue is a stock: it holds work until a flow moves that
work elsewhere. Arrivals, admission, execution completion and review are the
flows in this model. Review limits throughput for B and C after startup. The
WIP cap balances admission by keeping new tasks in the admission queue until a
decision frees a place. That queue remains inside the system we measure.

The measurement boundary changes what appears faster. If we count only time
spent awaiting review, C looks much faster. Counting admission wait as well
shows where the waiting moved and that B and C complete tasks at the same
ticks. This is an interpretation of the teaching model, not a quoted result or
experiment from *Thinking in Systems*.

## Reproduce and inspect the evidence

From the repository root:

```sh
make review-capacity-demo
```

This runs the existing CLI with the committed dependencies and fixed
`experiments/review-capacity/scenario.json` scenario. You can run the same
experiment directly with:

```sh
uv run --locked systems-lab experiment review-capacity \
  --scenario experiments/review-capacity/scenario.json
```

The command prints a manifest naming the new attempt directory under
`.lab/experiments/review-capacity/`. It contains `scenario.json`, `report.json`
and the completion marker `manifest.json`. Running this numerical experiment
does not create control credentials, start agent workers or providers, request
approval, or write to the canonical audit journal.

Each run creates a fresh attempt. Repeating the same input produces identical
report bytes and hash, while reusing an explicit `--attempt-id` is rejected.
`status: complete` means the artifact files were completed; numerical
`drain.complete` separately says whether all tasks finished before the drain
bound.

The graphics were regenerated from a CLI export on **5 October 2026**. Their
[frozen documentation projection](../../docs/graphics/review-capacity/evidence.json)
contains teaching traces and metrics without runtime event or attempt IDs.
Original attempts stay in ignored `.lab/`. These are **not dashboard screenshots,
operational history or OpenTelemetry measurements**.

| Reference | SHA-256 |
| --- | --- |
| Scenario | `77c8a82e574cf23eb7bd1babd76332daa1a04926309f34427f638d1f29d3fae3` |
| Deterministic report | `a3a9c0396620438fa7c039f5aa9aace98a85cff968ba5004c52e5e25f473e58a` |

Hashes let you detect when a file differs from a preserved reference. Someone
with sufficient local privileges can rewrite both the file and its hash, so
they do not make these files immutable storage. An independently retained
reference would support a stronger claim about their history.

## Try to disprove the explanation

1. Change only C's `wip_limit` from 3 to 2. Does review become starved, and does
   full-drain time increase? Inspect utilization and both queues.
2. Change `review_ticks` from 6 to 3 for all policies, keeping the rest fixed.
   Does the limiting stage move toward execution? Compare the common horizon
   and complete cohort separately.
3. Before transferring this idea to actual agents, specify rework, failures,
   quality and permission-release semantics. That is a separate runtime
   experiment; the current numerical model cannot validate them.

## Limits and current delivery status

Every review accepts. Arrivals are finite and scheduled; service is uniform.
There is no stochasticity, priority, output quality, rework, fatigue, failure,
real human approval or empirical relationship to a team's throughput.

**Review Capacity v0.2 is complete and closed as of 20 October 2026.** The bounded
model, exclusive exports, CLI, fixed scenario, `make review-capacity-demo`,
viewer-authorized API and integrated comparison/replay meet the accepted scope.
The [closure record](../../docs/openspec/changes/archive/2026-10-20-review-capacity-experiment/verification.md)
maps all eight requirements to implementation and evidence. OpenSpec synchronized
the [canonical specification](../../docs/openspec/specs/review-capacity-experiment/spec.md)
and archived the change.

The scenario validator
limits `observation_horizon` to 0..10000 ticks and keeps `drain_deadline` at or
below 50000 ticks.

Fresh closure validation passed Ruff, 131 tests and Compose configuration
validation, with five opt-in container tests skipped. The demo reproduced report
SHA-256
`a3a9c0396620438fa7c039f5aa9aace98a85cff968ba5004c52e5e25f473e58a`.

The separate [fixture-workflow admission experiment](../fixture-workflow-admission/README.md)
now tests admission against actual fixture workflows, with two tasks and WIP
capped at one per batch. It preserves explicit operator decisions. That runtime
evidence does not turn this numerical model into a productivity measurement.

The integrated dashboard reads these saved reports through the viewer-
authorized API. To try it, start the gateway and dashboard, generate a saved
attempt, then open **Experiments** and refresh the report list:

```sh
make dashboard
# In another terminal:
make review-capacity-demo
```

Connect with `.lab/viewer.token`. The list includes complete, verified reports;
choose one to compare policies at the shared horizon and replay task positions.
The dashboard handles loading, empty results and retryable read failures. It
does not create attempts or run the simulation in the browser. Compose does not
mount host experiment reports, so this flow uses the local gateway and its
`.lab/experiments/review-capacity` data.

The standalone learning guide remains an offline documentation artifact; it
does not replace the gateway's saved-report reader or establish live-model
quality.

### Read-only report API

The local gateway exposes two viewer-authenticated JSON endpoints:

| Request | Response |
| --- | --- |
| `GET /api/experiments/review-capacity` | `{ "attempts": [...] }`, containing up to 50 verified manifests after scanning at most 200 directory entries. |
| `GET /api/experiments/review-capacity/{attempt_id}` | `{ "manifest": ..., "scenario": ..., "report": ... }` for one verified attempt. |

The operator and viewer credentials are accepted; worker credentials are
rejected. The gateway CLI configures the storage root from `LAB_ROOT` (default
`.`) as `$LAB_ROOT/.lab/experiments/review-capacity`. Requests cannot provide a
filesystem path. An absent root produces an empty list, while a missing attempt
returns 404. Incomplete or invalid attempts are omitted from listing; a direct
read of one returns a generic 422. Storage errors return a generic 503.

The reader verifies strict JSON, complete manifests, byte hashes and file
integrity. It rejects symlinked roots, parent directories, attempt directories
and data files. Manifest and scenario files may each be at most 16,384 bytes;
reports may be at most 5,242,880 bytes. Responses use `application/json` and
`Cache-Control: no-store`. These read-only requests do not create files or
change runs, decisions or the canonical journal. Container report mounting is
not implemented.
