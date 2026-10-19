# Development

## Setup and checks

```sh
make setup
make check
make spec-check
```

`make check` runs Ruff lint/format checks, pytest, and Compose configuration
validation. Container integration tests are skipped unless explicitly
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
  journal.py            # Append-only history, integrity and delivery outbox
  activity.py           # Read-only activity projection
  telemetry.py          # Stable OpenTelemetry export from durable events
  static/               # Same-origin live browser dashboard
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

## Read exported experiments

The [Review Capacity guide](../experiments/review-capacity/README.md) documents
the viewer-authorized report listing and detail endpoints. The CLI binds reads
to `LAB_ROOT/.lab/experiments/review-capacity`, with `LAB_ROOT` defaulting to the
working directory. Direct `create_app` callers can set the trusted
`experiment_root` keyword; its default is the same relative layout under the
working directory. Request parameters cannot change this root.

Reads validate complete manifests, file hashes and size bounds, and reject
symlinks in the root, its parents, attempt directories and data files. Missing
roots list as empty; storage errors remain errors. These reads do not create
attempts or operational events. Compose does not mount host experiment reports;
container report import remains outside this slice.

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

The JSON is a **frozen documentation projection** with numerical task IDs and
timestamps, not runtime attempt IDs or lifecycle-event identities. Raw exports
remain ignored under `.lab/`. Keep generated assets in Git so Markdown images
work without a running application; open HTML locally because GitHub shows its
source. To preview it over localhost:

```sh
python -m http.server 8877 --bind 127.0.0.1 \
  --directory docs/graphics/review-capacity
# Open http://127.0.0.1:8877/explainer.html
```

Compare the documented numbers and hashes with the source report. Inspect figure
labels and legends, desktop/mobile layout, policy selection, seek, playback and
reduced motion. Verify task counts at startup, the horizon and full drain.
The page uses embedded data and no operational requests or credentials.
If the scenario changes, update the prose and interpretation alongside the figures.

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
SVGs from `docs/images/dashboard/`. The README reuses `overview.jpg`.
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

The October update uses desktop captures only. The guide records the isolated
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
