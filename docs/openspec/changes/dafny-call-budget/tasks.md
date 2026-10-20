# Implementation tasks

All tasks are pending. This is a planning proposal; no Dafny result is claimed.
The design and delta spec define this change's scope; do not maintain a second
implementation plan elsewhere.

## 1. Characterize the Existing Behavior

- [ ] Add the limit-2 researcher test: wrong-role denial, two permitted calls,
      then exhaustion; assert the operator snapshot reports `used_calls = 2`.
- [ ] Add the limit-1 reviewer test: missing simulation returns 409, consumes
      one slot, and the next attempt is budget-denied; assert `used_calls = 1`.
- [ ] Run the focused gateway tests through `make test` with `PYTEST_ADDOPTS`;
      retain the existing limit-1 regression. These characterization tests
      should pass without production changes.

## 2. Demonstrate and Prove the Budget Contract

- [ ] Set up and record one official Dafny release, checksum and solver version
      locally under `.lab/`; document the reproducible setup command.
- [ ] Define the contract and an isolated `<=` negative variant; observe its
      failed budget obligation at `used = limit = 1` before correcting the model.
- [ ] Implement the `<` model and prove P1-P5 from `design.md`, including finite
      sequences and deactivation; verify concrete satisfiable state witnesses.

## 3. Reproduce, Interpret and Close

- [ ] Add the opt-in `make call-budget-verify` target and small runner; require
      positive verification and the expected negative-control diagnostic.
- [ ] Write the experiment guide and index link; map P1-P5 to Python evidence,
      record uncovered assumptions, and preserve raw evidence under `.lab/`.
- [ ] Run `make call-budget-verify`, `make check`, `make spec-check` and
      `git diff --check`; report unavailable or skipped checks explicitly.
- [ ] Review every claim against evidence, then sync and archive only when the
      experiment is implemented and its acceptance scenarios are satisfied.
