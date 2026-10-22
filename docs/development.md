# Development

A useful experiment has a testable hypothesis and makes clear what its results
can establish. This guide walks through the repository steps for adding one,
from defining the model boundary to retaining evidence. A simulation result
does not establish agent behavior or quality, and a workflow run does not
validate the simulation model.

## Setup and checks

```sh
make setup
make check
make spec-check
```

`make check` runs Ruff lint and format checks, pytest, and Compose configuration
validation. The pytest suite includes `tests/test_review_capacity_frontend.py`.
That test passes an actual deterministic fixture report, generated from fixed
test data, to the browser projection's Node built-in test runner. The test
reports a clear skip if Node.js is unavailable and adds no npm dependencies.
Container integration tests are skipped unless you enable them explicitly.
`make spec-check` requires the OpenSpec command-line interface (CLI); the
bootstrap used version 1.10.0.

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
  journal.py            # Append-only history, integrity and delivery outbox
  activity.py           # Read-only activity projection
  telemetry.py          # Stable OpenTelemetry export from durable events
  static/               # Same-origin live browser dashboard
    experiments.js      # Saved Review Capacity report view and replay
experiments/            # Scenarios, hypotheses, interpretation and reading notes
tests/                  # Numerical, authorization, workflow and container checks
docs/openspec/          # Current requirements and reviewable changes
```

## Add an experiment

Start with the experiment guide and one behavior-level test. Keep deterministic
model calculations independent of the agent framework so you can interpret
model results without attributing them to an agent. Extend the gateway with a
typed operation that limits the resources it can use, then explicitly grant it
to the needed role. The gateway must continue to deny unknown operations.

Add a real model only through an explicit gateway route change and evaluation.
Do not inject provider keys into workers or claim fixture results establish
model quality. Do not add an unrestricted URL proxy or shell to simplify an integration.

## Read exported experiments

The [Review Capacity guide](../experiments/review-capacity/README.md) documents
the viewer-authorized report listing and detail endpoints used by the dashboard's
separate Experiments view. The CLI binds reads
to `LAB_ROOT/.lab/experiments/review-capacity`, with `LAB_ROOT` defaulting to the
working directory. Direct `create_app` callers can set the trusted
`experiment_root` keyword; its default is the same relative layout under the
working directory. Request parameters cannot change this root.

Reads validate complete manifests, file hashes and size bounds. They also reject
symbolic links in the root, its parents, attempt directories and data files, so
the configured report root cannot silently point elsewhere. A missing root
produces an empty list; storage errors remain errors. Reads do not create
attempts or operational events. Compose does not mount host experiment reports,
so importing reports into a container is outside this change.

## Refresh the numerical learning graphics

The [review-capacity learning guide](../experiments/review-capacity/README.md)
uses figures derived from an actual deterministic CLI export. Its standalone
HTML replay is documentation, separate from the Activity dashboard.

1. Run the experiment command from that guide and retain the printed attempt ID.
2. Generate the assets from that attempt's report:

```sh
make review-capacity-figures \
  REPORT=.lab/experiments/review-capacity/ATTEMPT_ID/report.json
```

Matplotlib is a temporary documentation tool; the application dependencies and
lockfile remain unchanged. The generator checks the scenario, conservation,
capacity and horizon counts before creating SVG/PNG charts, `evidence.json` and
the self-contained `explainer.html`. `flow.svg` is the separately authored model
boundary diagram; `explainer.template.html` contains the learning-page layout.

The JSON is a **frozen documentation projection**: its task IDs and timestamps
belong to the numerical model, not to runtime attempts or lifecycle events.
Raw exports remain ignored under `.lab/`. Keep the generated assets in Git so
Markdown images work without a running application. Open the HTML locally,
because GitHub displays its source. To preview it over localhost:

```sh
python -m http.server 8877 --bind 127.0.0.1 \
  --directory docs/graphics/review-capacity
# Open http://127.0.0.1:8877/explainer.html
```

Compare the documented numbers and hashes with the source report. Inspect figure
labels and legends, desktop/mobile layout, policy selection, seek, playback and
reduced motion. Verify task counts at startup, the horizon and full drain.
The page uses embedded data, makes no operational requests and uses no
credentials.
If the scenario changes, update the prose and interpretation alongside the figures.

## OpenSpec

`openspec` at the root is a symbolic link to `docs/openspec/`. Use the shared
OpenSpec workflow to propose, implement, verify and archive meaningful changes.
It keeps requirements and their evidence reviewable:

```sh
openspec list
openspec list --specs
openspec validate --all --strict
```

Keep requirements focused on the current experiment. The roadmap describes
proposals; it does not mean those capabilities have been implemented.

Review Capacity v0.2 is closed. Its canonical requirements live in
`openspec/specs/review-capacity-experiment/spec.md`; the archived change contains
the requirement-to-evidence map in `verification.md`. The separate
[fixture-workflow admission experiment](../experiments/fixture-workflow-admission/README.md)
adds actual process coordination without changing that numerical model.

Fixture batch writes execute only in the local CLI gateway. `POST /batches`
accepts an optional UUID and creates two copies of the fixed backlog scenario;
`GET /batches/{id}`, `POST /batches/{id}/advance` and
`POST /batches/{id}/reconcile` require operator authorization. A gateway without
a configured local coordinator rejects batch creation/advance/reconcile.
Batch and item tables are additive. A transaction binds each item to its run.
Owner epochs (generation numbers for the current owner) reject mutations from
an earlier owner. A POSIX (Unix-style) file lock inherited by workers covers the
graph invocation and batch decisions. Admission does not assume an uncertain
worker has stopped just because its journal entry was delivered, the CLI exited
or a checkpoint exists.

Use `PYTEST_ADDOPTS='tests/test_admission.py tests/test_admission_store.py
tests/test_admission_access.py tests/test_admission_recovery.py
tests/test_admission_processes.py' make test` for focused checks. Process tests
use temporary local state and loopback servers. Five existing opt-in container
tests are still separate; they do not validate container batch admission.

With OpenSpec 1.10.0, archive from `docs/` so the CLI operates on the physical
OpenSpec directory. Archiving through the root symlink can fail its final-move
integrity check; validation and listing work from the repository root.

```sh
cd docs
openspec archive CHANGE_NAME --yes
```

## Local state

`.lab/control.db` stores local operational evidence; `.lab/checkpoints.db`
stores workflow checkpoints; `.lab/runs/<run-id>/` contains JSON exports.
The Compose operational store lives in its named Postgres volume. Operator
credentials, databases, and artifacts stay out of Git and Docker build context.

The observability migration is additive: it imports the previous events table
once, retains and seals that table, and marks imported evidence explicitly.
Stop older gateway processes before upgrading. Never delete existing experiment
evidence to accommodate a schema change. See [observability](observability.md)
for history verification, external checkpoints, the dashboard and OTLP delivery.

## Refresh the dashboard screenshots

The [dashboard guide](dashboard.md) embeds browser captures and two annotated
SVGs from `docs/images/dashboard/`. The README uses a separate 16 October capture
set in `docs/images/readme/`, with its own `captures.json`: a fresh three-process
fixture run against an isolated gateway, with telemetry export disabled.
Current JPG captures replace the older PNG tour in the guide; the earlier PNG
files remain historical assets.

1. Use a separate local capture session. Either observe `make dashboard-demo`
   through its gateway, or use an isolated gateway with clearly labelled test
   fixtures. Record which method supplied the events. Do not change the normal
   workspace's credentials, evidence or permissions to obtain a screenshot.
2. Capture the empty connection form before entering a credential. Connect using
   the correct viewer token for that gateway. Confirm the input is cleared.
3. Select a run waiting for review. Capture the overview and each module below.
   Do not edit DOM values, paint fake states or treat seeded lifecycle events as
   proof of real worker execution.
4. Compare a saved test checkpoint through the read-only verifier. Capture a
   match, then a deliberately altered test checkpoint's mismatch. Change the
   test file, not canonical history. Keep raw checkpoint files ignored.
5. In the isolated capture environment, provoke an activity-read failure and
   capture the stale state. Record the failure method, restore successful reads
   and leave the normal gateway unaffected.
6. Add numbered SVG notes around the unchanged captures. Check that the notes
   match the visible values and do not imply stronger guarantees than the UI.
7. Inspect the graphics in a browser, verify every local Markdown link and record
   capture time, context, source hashes and image hashes in `captures.json`.

The Activity screenshot set uses desktop captures. The guide records the isolated
fixture gateway, disabled exporter and seeded worker lifecycle records. The
browser's screenshot API returns JPEG. Capture geometry and zoom are recorded
with the evidence; do not claim that a screenshot proves animation or process
health. No credentials, headers, private traces or developer panels belong in
public images.

| Asset | Capture target |
| --- | --- |
| `connect.jpg` | Empty connection form |
| `overview.jpg` | Work states, delivery queue, session charts and configured map |
| `metrics.jpg` | Four independent status cards |
| `work-and-delivery.jpg` / `work-and-delivery-annotated.svg` | Task counts, oldest waits and delivery count |
| `session-trends.jpg` | Two separate charts of browser-session readings |
| `system-map.jpg` | Configured components and the history-check caption |
| `runs.jpg` / `run-inspector.jpg` | Selected run and reported workflow stage |
| `operator-controls.jpg` | CLI commands, role tools and recorded lifecycle times |
| `events.jpg` | Actions with expandable evidence and IDs |
| `checkpoint-match.jpg` / `checkpoint-annotated.svg` | Matching earlier checkpoint after a later event |
| `checkpoint-mismatch.jpg` | Deliberately altered test checkpoint |
| `connection-lost.jpg` | Failed activity read and cached last verification |

The Review Capacity view has a separate full-page desktop and mobile capture
set in `docs/images/review-capacity-dashboard/`, with source and image hashes
in its `captures.json`. Capture it from an isolated local gateway using a
synthetic fixture report. Keep the **SIMULATION REPLAY** label visible and
caption the images as model evidence, not live agent or team performance. The
captures should show both the common-horizon policy comparison and the
task-level flow; do not alter browser content to manufacture values.
