# Implementation tasks

Slice 1 closure on 19 October 2026: the numerical model, CLI, exclusive exports,
fixed scenario and Make demo target are implemented. The observation horizon is
bounded to 0..10000 ticks; the drain deadline remains bounded to 50000 ticks.
Slice 2 is implemented: the viewer-authorized API supplies the dashboard's
comparison, SVG charts and local task replay. Desktop/mobile browser checks and
documentation are complete. The change was synchronized and archived on
20 October 2026; all eight requirements are now in the canonical specification.
The model/export test files passed 51 tests and the fixed demo completed with
the reference report hash. Full validation results are recorded below.

## Slice 1: reproducible numerical comparison

- [x] Add a behavior test with manually checkable arrivals/service that proves
      task conservation, FIFO order, service timing and exact decision times.
- [x] Implement the pure event-time model and strict bounded scenario validation,
      including the 0..10000 observation-horizon bound and drain deadline of at
      most 50000 ticks.
- [x] Add the 24-task A/B/C scenario, version, boundary, hypothesis and units.
- [x] Test that total WIP includes review service and awaiting-review work;
      finishing execution must not release its WIP slot.
- [x] Test common-horizon pending counts, zero-completion metrics, full drain,
      tied events, exhausted drain bound and invalid inputs.
- [x] Derive queue/occupancy/wait/throughput metrics from trace and reconcile
      summaries independently; document percentile and time-weighting methods.
- [x] Add the experiment CLI and Make demo target; exclusively export complete
      attempts with deterministic report hashes and synthetic provenance. The
      demo target runs the locked CLI with the fixed scenario.
- [x] Test repeated input equality, new-attempt creation and overwrite rejection;
      verify no gateway journal, worker, approval or provider action is invoked.

## Slice 2: read-only experiment dashboard

- [x] Add bounded, ID-based report listing/loading under the configured local root,
      checking complete manifests, hashes and viewer authorization.
- [x] Test path traversal, oversized/incomplete/altered reports and read-only
      access; preserve the existing Activity endpoint contract.
- [x] Add A/B/C metrics and SVG charts, showing horizon and pending sample counts.
- [x] Add logical-tick flow playback with play/pause, seek, speed and reduced
      motion; prominently distinguish simulation replay from live agent activity.
- [x] Inspect desktop/mobile presentation and empty/loading/error states using
      real browser rendering; confirm playback performs no operational writes.

## Slice 3: evidence and documentation

- [x] Run the fixed comparison, export original reports and reconcile all counts.
- [x] Write observations that support or contradict the hypothesis, with explicit
      upstream waiting, pending-work and synthetic-review limits.
- [x] Update the experiment guide, dashboard guide, user README and development
      guide for commands/features that have actually been implemented.
      The guides cover the integrated Experiments view and the complementary
      offline learning artifact.
- [x] Capture a readable comparison and flow view with simulation labels intact.
      Integrated desktop/mobile captures and source/image hashes are in
      `docs/images/review-capacity-dashboard/`.
- [x] Run `make check`, `make spec-check` and `git diff --check`; report unavailable
      checks accurately. On 20 October 2026, `make check` passed Ruff, 131 tests
      and Compose configuration validation; 5 opt-in container tests were
      skipped. `make spec-check` passed all 5 items and `git diff --check` passed.
- [x] Sync/archive only after required work is complete. OpenSpec added eight
      requirements to `specs/review-capacity-experiment/spec.md` and archived the
      change as `2026-10-20-review-capacity-experiment`. See `verification.md`.

Slice 2 verification on 20 October 2026: targeted frontend, API and Activity
checks passed 49 tests. The frontend wrapper ran seven Node tests against actual
model reports, including zero-horizon and incomplete-drain data. In the browser,
the fixed comparison matched 6/8/8 decisions and 18/16/16 unfinished tasks at
tick 60. Policy changes, keyboard seek, play/pause, speed, horizon/end jumps,
reduced motion, loading, empty results, a 503 error/retry and lock during loading
were exercised. Playback and navigation added zero report requests (12 before
and after); the isolated session used GET requests only, with zero journal
events or runs. The interface finish review returned `ship` for desktop and
mobile. Container report mounting is not implemented.

## Follow-on boundary

Actual fixture concurrency/admission, live models and automatic real-run approval
are not implementation tasks in this change. Draft their own proposals after
the numerical comparison and its limitations are understood.
