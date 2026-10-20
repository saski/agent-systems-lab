# Review Capacity v0.2 verification

Date: 20 October 2026. Implementation reference: `0e1a186`.

The implementation meets all eight requirements in this change. No additional
runtime behavior was needed during closure. OpenSpec synchronization and
archival completed after this verification.

## Requirement coverage

| Requirement | Implementation and evidence |
| --- | --- |
| Bounded deterministic model | `review_capacity.py`; model tests cover repeatability, validation, tied events, capacities and the independent 10000-tick horizon bound. |
| Controlled A/B/C comparison | The fixed scenario and `test_24_task_scenario_full_drain`; only execution slots or admission cap differ between adjacent policies. |
| Total WIP and visible upstream waiting | Model admission logic and WIP tests count execution, waiting for review and review service until a decision; the guide and replay retain upstream tasks. |
| Trace-reconciled metrics and incomplete work | `review_capacity_metrics.py` and model tests cover horizon/drain cohorts, task conservation, future arrivals, null percentiles and exhausted drain bounds. |
| Separate synthetic evidence and preserved attempts | `review_capacity_exports.py`, export tests and the CLI keep synthetic attempts exclusive, deterministic and separate from gateway history. |
| Authenticated bounded report access | Gateway GET endpoints, the export reader and HTTP tests cover viewer/operator authorization, worker rejection, path traversal, symlinks, content bounds, hash mismatch and read-only behavior. |
| Clearly labeled playback | Static Experiments assets, seven Node projection tests through pytest and the browser capture manifest cover charts, task states, controls, reduced motion, loading/empty/error states and independence from Activity. |
| Evidence-bounded interpretation | The experiment guide records the hypothesis, controlled inputs, observations, both queues, incomplete cohorts and limits; it makes no real-agent quality or productivity claim. |

## Fresh verification

- `make check`: Ruff lint and format checks, 131 passing tests and Compose
  configuration validation; five opt-in container tests skipped.
- `make review-capacity-demo`: complete attempt
  `a9eb0f7273f84778a93abd9185748e1d`, with deterministic report SHA-256
  `a3a9c0396620438fa7c039f5aa9aace98a85cff968ba5004c52e5e25f473e58a`.
- The regenerated report reconciles horizon decisions A/B/C = 6/8/8,
  unfinished tasks = 18/16/16, and final decision ticks = 198/152/152.
- All six source hashes and both screenshot hashes in
  `docs/images/review-capacity-dashboard/captures.json` match the current files.
  The browser checks were performed on 20 October; closure verifies their source
  identity rather than claiming a new browser session.
- The frozen standalone learning graphics retain their own earlier capture and
  generation dates; they are distinct from the integrated dashboard captures.
- `node --check` passed for `experiments.js`, `review-capacity.js` and `app.js`.
- After archival, `make spec-check` passed strict validation of all active
  change/specification items. `git diff --check` passed.

## Scope boundary

Container report mounting/import, real fixture-workflow admission, live models,
review quality, rework and automatic real-run decisions were not v0.2 acceptance
requirements. Existing five container integration tests were not executed in
this closure. The numerical reviewer accepts every task; its logical ticks are
not operational time or evidence of human review quality.

## Closure outcome

OpenSpec 1.10.0 archived the change from the physical `docs/openspec/` directory
as `2026-10-20-review-capacity-experiment`, with specification updates enabled.
It added all eight requirements to
`docs/openspec/specs/review-capacity-experiment/spec.md`; no requirements were
removed. All 19 implementation/closure tasks are complete.

The next fixture-workflow admission change is a separate proposal, not an
implemented continuation or a new completion requirement for v0.2.
