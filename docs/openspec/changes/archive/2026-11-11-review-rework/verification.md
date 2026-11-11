# G02 verification — 11 November 2026

G02 implements the approved comparison of review order when six of 24 tasks
require a correction. It is a local numerical experiment. No public post,
deployment, provider access or operational approval was added. The numerical
experiment is complete; extending the public demo is a separate follow-up.

## Requirements and evidence

| Requirement | Implementation and verification |
| --- | --- |
| Paired deterministic review-order experiment | `src/systems_lab/review_rework.py`, fixed `experiments/review-rework/scenario.json`; hand-calculated four-task test, simultaneous completion/return, non-preemption, execution FIFO, identical no-correction traces, strict input bounds and deterministic repeated output |
| Complete task accounting and honest latency metrics | Separate attempts and decisions, conserved task stocks, cohort-size/observed/pending counts, null summaries for incomplete or empty cohorts; independent interval reconstruction, shared execution contention, deadline-zero and partial-drain tests |
| Reproducible local evidence without runtime actions | CLI and Make entry points, existing exclusive bounded export writer extended to the new type; byte-identical repeated reports, hash checks, no-overwrite and invalid-ID tests, no runtime state initialization, external gateway rejected, existing report reader rejects G02 reports |
| Learning evidence and boundaries | Experiment guide, per-task comparison figure, saved evidence projection, root/experiment/development/roadmap links; fixed costs and correction needs are explicit assumptions |

The first behavior test failed because the model was absent, then passed after
implementation. Three CLI/export tests subsequently failed because the new
experiment type was unsupported, then passed after that integration.

## Validation

- `make check`: Ruff lint and formatting passed; **204 tests passed**, with five
  opt-in container tests skipped; Compose configuration validation passed.
- The first restricted run could not bind local test servers. The complete run
  above was repeated with local-server access and passed in 53.02 seconds.
- `make spec-check`: eight active changes/specifications passed both before and
  after archival; the final run includes the canonical G02 specification.
- `git diff --check`: passed.
- `make review-rework-demo`: two distinct exports had identical report bytes.
- `make review-capacity-demo`: preserved the original v0.2 reference report hash
  `a3a9c0396620438fa7c039f5aa9aace98a85cff968ba5004c52e5e25f473e58a`.
- `make review-rework-figures REPORT=...`: generated PNG, SVG and evidence JSON
  from the saved report, using already cached Matplotlib in offline mode. The
  PNG was visually inspected for readable labels and complete chart content.

No application dependencies or lockfile changed. Container runtime integration
was not exercised; its five tests remain explicitly skipped.

The OpenSpec archive command reported a final-move fingerprint mismatch and
rolled back its attempted changes. The three added requirements were then
synchronized directly into the canonical specification and the completed change
moved to `archive/2026-11-11-review-rework`. A byte-hash comparison confirmed all
five files were preserved by the move; canonical requirement text exactly
matched the delta. Only this closure record and the final task checkbox were
updated afterward. The archival issue did not require changing the CLI tool or
weakening any project check.

## Numerical reconciliation

Two CLI attempts are retained under ignored `.lab/experiments/review-rework/`:
`05b991ed53f348f8a28f7694f5011b15` and
`649f266506ff4d1c89bd6168eecbe300`.

- Scenario SHA-256: `ad94cf6b6acda5f804d3a5d4d8042cfd7085fa2d7fecac1f1c8f6542e72bb133`
- Report SHA-256: `3f1f1dff0790d109c7f814377cb0acf3088829d2c0ecff78317b7e7eb9577097`

An additional check read the exported traces without calling the simulator. It
verified all 30 review choices per policy against ready attempts, service times
and non-overlap. It reconstructed every stock from task intervals at all 55 FIFO
and 56 priority sample ticks. The area under unfinished work equals the sum of
arrival-to-acceptance times: **1908 FIFO, 1840 priority**. Both traces consume
216 execution-slot ticks and 180 reviewer ticks. The local audit record is
`.lab/g02-2026-11-11/trace-verification.json`.

Correction priority reduces mean turnaround from 79.50 to 76.67 ticks, while
five tasks finish earlier, fifteen later and four unchanged. Corrected-task
mean falls from 137.00 to 92.67; first-pass mean rises from 60.33 to 71.33.
Ready-to-first-review waiting rises from 48.17 to 59.42. Full-batch completion
moves from tick 188 to 192 because the reviewer is idle during the final
correction from 182 to 186. These findings apply to the fixed synthetic model.

The tracked figure and evidence projection are in
`docs/graphics/review-rework/`; the learning guide is
`experiments/review-rework/README.md`. The source report contains complete
attempts and paired per-task differences, including the last corrected task
that finishes later under priority.
