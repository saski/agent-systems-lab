# Implementation tasks

Partial delivery on 5 October 2026: the numerical model, CLI and exclusive
exports are implemented in this working branch. Their 50 tests pass. The
illustrated learning guide is standalone documentation; integrated dashboard
delivery and full-change acceptance remain pending.

## Slice 1: reproducible numerical comparison

- [x] Add a behavior test with manually checkable arrivals/service that proves
      task conservation, FIFO order, service timing and exact decision times.
- [ ] Implement the pure event-time model and strict bounded scenario validation.
      The model exists; its observation-horizon maximum is currently 50000,
      whereas the design selects 10000. Align that bound before full acceptance.
- [x] Add the 24-task A/B/C scenario, version, boundary, hypothesis and units.
- [x] Test that total WIP includes review service and awaiting-review work;
      finishing execution must not release its WIP slot.
- [x] Test common-horizon pending counts, zero-completion metrics, full drain,
      tied events, exhausted drain bound and invalid inputs.
- [x] Derive queue/occupancy/wait/throughput metrics from trace and reconcile
      summaries independently; document percentile and time-weighting methods.
- [ ] Add the proposed experiment CLI and Make demo target; exclusively export
      complete attempts with deterministic report hashes and synthetic provenance.
      CLI/export behavior is verified; the Make target remains pending.
- [x] Test repeated input equality, new-attempt creation and overwrite rejection;
      verify no gateway journal, worker, approval or provider action is invoked.

## Slice 2: read-only experiment dashboard

- [ ] Add bounded, ID-based report listing/loading under the trusted local root,
      checking complete manifests, hashes and viewer authorization.
- [ ] Test path traversal, oversized/incomplete/altered reports and read-only
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
      checks accurately. The publication package passes 83 tests with 5 container
      tests skipped by default, Ruff/Compose checks and all 4 OpenSpec items.
- [ ] Sync/archive only after required work is complete.

## Follow-on boundary

Actual fixture concurrency/admission, live models and automatic real-run approval
are not implementation tasks in this change. Draft their own proposals after
the numerical comparison and its limitations are understood.
