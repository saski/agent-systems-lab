# Fixture-workflow admission verification

Date: 21 October 2026. Implementation is an uncommitted change on top of
`2e9a482`. No live model, container batch execution or external write was enabled.

## Requirement coverage

| Requirement | Implementation and evidence |
| --- | --- |
| Bounded fixture batch | Operator-only API loads the fixed backlog fixture, creates two stable item identities and rejects caller-defined scenarios, task lists, paths and WIP. API/CLI tests cover input bounds, idempotent creation and rejection without a local coordinator. |
| Durable single-owner admission | `admission_store.py` atomically reserves and binds one run; tests use independent Store connections, a failing SQL binding trigger and stale epochs. Two actual coordinator processes compete while the fixture graph is held at a real HTTP boundary; the second cannot launch. |
| Review retains WIP | Real fixture tests reach `awaiting_review`, preserve the first run and worker count across restart, and retain the second item without a run. Accept, reject and confirmed revocation release the place once. Ambiguous launch and gateway failure retain it. |
| Authorization and checkpoint isolation | Missing, viewer and worker credentials are rejected for batch operations. Stale digest, unauthorized checkpoint resume and a competing batch decision cannot advance. Existing digest-bound decisions use distinct run/checkpoint IDs and the batch lock. |
| Separate fixture evidence | CLI demonstration and derived exports retain batch/item/run IDs, timestamps and `fixture_workflow` provenance. Numerical exports are untouched. Reports contain no operator credentials and make no productivity or live-model claim. |

The inherited-lock parent-death test uses a controlled child process that remains
alive across parent `SIGKILL`; takeover stays blocked until that child exits.
The next advance still blocks the ambiguous run until explicit terminal
reconciliation. This tests process exclusion, not arbitrary exactly-once worker
execution. A separate real-worker failure test revokes the run, preserves WIP
and requires reconciliation without repeating that worker.

## Isolated CLI demonstration

The demonstration ran the public Make targets in a fresh state root:
`.lab/fixture-admission-20261021-vkhd9o8i`.

- Batch: `91ecc522-247d-459a-ab5d-36109830dd8c`.
- First run: `246d46b1-ae17-4eb7-b94c-6b4e217ad536`.
- Second run: `088d26d4-c1ce-4db6-82e7-a823070c0971`.
- First advance: three completed specialists, first item awaiting human review,
  second item queued with no run, WIP one.
- Repeated advance in a new CLI process: identical item state, no extra worker.
- Explicit operator approval of the first digest, followed by advance: the first
  item released and the second run admitted exactly once.
- Explicit operator rejection of the second digest, followed by advance: both
  items released, outcomes `accepted` / `rejected`, WIP zero and six completed
  specialists across the batch.

The harness issued each test decision as a separate operator command. The
coordinator contains no automatic acceptance, rejection or retry policy.
Full command results and source hashes are saved under that state root at:
`.lab/experiments/fixture-workflow-admission/91ecc522-247d-459a-ab5d-36109830dd8c/`.
The `verification.json` SHA-256 is
`1f7fd62dedd49f9bdece2907ead93fbcb796cbe551eed8cd86daec18b6675191`.
These ignored files are local evidence, not published or immutable storage.

## Validation and limits

- `make check`: Ruff lint/format, 146 passing tests and Compose configuration
  validation. Five opt-in container tests were skipped.
- The 15 new admission test cases cover Store transactions, HTTP access, CLI,
  real fixture workers, two coordinator processes and inherited-lock recovery.
- `make spec-check`: seven active change/specification items passed strict validation.
- `git diff --check`: passed.
- Independent read-only review found and prompted fixes for unsupported gateway
  creation and caller-supplied scenarios; follow-up review found no remaining
  blocking issue in the admission boundary.

OpenSpec synchronized all five requirements into the canonical specification
and archived this change as `2026-10-21-fixture-workflow-admission`. All 12
acceptance tasks are complete. Post-archive strict validation also passed.

Acceptance is local POSIX process execution and SQLite with WIP one per batch.
The model assumes a trusted coordinator, local filesystem and unchanged lock
files in one state root. It does not prove distributed ownership, protect against
a privileged local attacker or impose a global cap across multiple batches.
Container/Postgres admission, batch UI, parallel scheduling, review quality,
live models and external actions remain separate work. No browser verification
was required because this slice changes no UI.
