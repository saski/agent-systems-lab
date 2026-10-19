# Implementation tasks

Slice 1 closure on 19 October 2026: the numerical model, CLI, exclusive exports,
fixed scenario and Make demo target are implemented. The observation horizon is
bounded to 0..10000 ticks; the drain deadline remains bounded to 50000 ticks.
The read-only HTTP report API and access tests for Slice 2 are implemented;
dashboard work, full-change acceptance and archival remain pending.
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
- [ ] Add A/B/C metrics and SVG charts, showing horizon and pending sample counts.
- [ ] Add logical-tick flow playback with play/pause, seek, speed and reduced
      motion; prominently distinguish simulation replay from live agent activity.
- [ ] Inspect desktop/mobile presentation and empty/loading/error states using
      real browser rendering; confirm playback performs no operational writes.

## Slice 3: evidence and documentation

- [x] Run the fixed comparison, export original reports and reconcile all counts.
- [x] Write observations that support or contradict the hypothesis, with explicit
      upstream waiting, pending-work and synthetic-review limits.
- [ ] Update the experiment guide, dashboard guide, user README and development
      guide for commands/features that have actually been implemented.
      Experiment/user/development guides and reproducible learning figures are
      available; integrated-dashboard documentation remains pending.
- [x] Capture a readable comparison and flow view with simulation labels intact.
      Standalone learning figures and a guide screenshot are available; the
      integrated dashboard remains part of pending Slice 2.
- [x] Run `make check`, `make spec-check` and `git diff --check`; report unavailable
      checks accurately. On 19 October 2026, `make check` passed Ruff, 130 tests
      and Compose configuration validation; 5 opt-in container tests were
      skipped. `make spec-check` passed all 5 items and `git diff --check` passed.
- [ ] Sync/archive only after required work is complete.

Slice 2 API status on 19 October 2026: the two read-only HTTP endpoints and
secure-access tests are implemented. Targeted API, export and Activity tests
passed (84 total, including 29 HTTP tests), and Ruff passed. This is partial
Slice 2 progress; the three dashboard tasks above, full-change acceptance and
archival remain pending. Container report mounting is not implemented.

## Follow-on boundary

Actual fixture concurrency/admission, live models and automatic real-run approval
are not implementation tasks in this change. Draft their own proposals after
the numerical comparison and its limitations are understood.
