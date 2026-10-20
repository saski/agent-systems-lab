# Call-budget model and evidence boundary

## Observed Starting Point

- [Store](../../../../src/systems_lab/store.py), `issue_grant` and `authorize`:
  each grant starts at zero; successful authorization increments once inside
  a transaction, with a conditional `used_calls < max_calls` update.
- [Gateway](../../../../src/systems_lab/gateway.py): the API accepts limits
  from 1 to 40. Authorization precedes operation execution. A reviewer lacking
  simulation evidence can consume a slot and then receive HTTP 409.
- [Gateway tests](../../../../tests/test_gateway.py):
  `test_gateway_keeps_runs_separate_and_bounds_operations` permits one call
  at limit 1 and rejects the next. Other tests separately exercise role denial
  and run revocation; they do not assert budget accounting for those denials.
- [Workflow test](../../../../tests/test_workflow.py),
  `test_three_specialists_pause_and_resume_after_restart_without_repeating_work`:
  asserts three consumed calls per specialist in one fixture workflow.

Planning validation: `make check` passed with 131 tests passed and 5 skipped,
including the gateway and workflow checks above. These are Python test
observations, not Dafny results. No experiment code was added during planning.

## Model and Properties

Model one already identified grant as `(used: nat, limit: nat, active: bool)`.
Initialize `used = 0`, `limit >= 1`, `active = true`; keep the limit fixed.
The proof generalizes beyond the API's finite 1..40 range.

For each request, an input `eligible: bool` summarizes the other authorization
checks, such as expiry and capability. Their correctness is assumed, not proved.
Each transition is atomic and represents a committed authorization decision:

```text
Request:
  allowed = active AND eligible AND used < limit
  nextUsed = used + 1 if allowed, otherwise used
  nextActive = active
Deactivate:
  nextUsed = used
  nextActive = false
```

`Deactivate` abstracts revocation or another run state that closes worker
access. The model has no reactivation or new-grant transition.

| ID | Property to prove |
| --- | --- |
| P1 | Every reachable state satisfies `0 <= used <= limit`. |
| P2 | A request is allowed exactly when active, eligible and below the limit; permission is not granted beyond those conditions or denied unnecessarily within this sequential model. |
| P3 | Allowed requests increment once; denied requests leave the counter unchanged. Deactivation changes no budget. |
| P4 | After deactivation, every later request is denied and preserves the counter. |
| P5 | For every finite transition sequence from initialization, `used` equals the number of allowed requests and never exceeds `limit`. |

Prove initialization and transition preservation, then P5 by induction over a
finite sequence. Include exhausted states in valid inputs: do not put
`used < limit` or `eligible` in the request method's precondition, which would
exclude the denial cases. Use no unproved `assume`, axioms, bodyless claims or
disabled verification to discharge these properties. Include concrete permitted,
exhausted and inactive witnesses so the contract is visibly satisfiable.

## Three Small Slices

1. **Characterize Python accounting.** Add a wrong-role denial followed by
   two permitted requests and exhaustion on a limit-2 researcher grant. Add a
   limit-1 reviewer case: missing evidence returns 409, then another attempt
   is denied for exhausted budget. Inspect `instances.used_calls` through the
   operator API. These tests are expected to pass the existing implementation;
   do not manufacture a production failure or change its behavior.
2. **Build the proof.** Add `experiments/call-budget-dafny/Budget.dfy` and
   pin an official Dafny release and its solver in the experiment guide. Begin
   with the isolated faulty guard and observe the failed obligation, then
   implement the correct model and prove P1-P5. The negative variant retains
   the same contract and arithmetic types as the valid model.
3. **Compare and reproduce.** Add the guide, negative variant and a small
   verification runner in that experiment directory. Add an opt-in
   `make call-budget-verify` target. It verifies all positive obligations and
   requires the negative variant to fail at the expected budget obligation;
   missing tools, syntax errors, crashes or timeouts are not a successful
   negative control. Keep Dafny outside default `make check` for this slice.

Expected files: `experiments/call-budget-dafny/{README.md,Budget.dfy,verify.py}`,
`experiments/call-budget-dafny/mutants/AllowAtLimit.dfy`, `Makefile`,
`tests/test_gateway.py` and a short experiment-index link. The guide records the
exact release, download checksum and solver version; setup stays local to the
experiment under `.lab/`, without modifying global tools or the Python lockfile.

Use `make test` with `PYTEST_ADDOPTS` for focused gateway checks, then
`make call-budget-verify`, `make check`, `make spec-check` and `git diff --check`.
The new verification target is proposed; it does not exist during planning.

## What The Comparison Can Establish

The existing limit-1 test would detect the same observable extra authorization
if present in the gateway. It does not execute the Dafny negative variant.
Python has two budget guards, so changing only one need not produce that faulty
behavior. The additional tests cover denied-call accounting and consumption
before tool failure. Dafny adds a universal result about the modeled sequences.
A test failure and an unproved obligation are different kinds of evidence; neither
proves all defects are absent. Timeout means no proof was obtained.

The model assumes atomic, durable steps. It does not prove SQLAlchemy, SQLite
or Postgres isolation, concurrent races, recovery, token identity, clock
correctness, compiler/solver correctness or the Python-to-model correspondence.
Keep the backend transaction mechanisms and their tests as separate evidence.
Revocation blocks later modeled authorization; it does not cancel an operation
already admitted. Each new grant has its own budget, so this is not a run-wide
cap, financial cap or bound on successful tool effects.

An omitted requirement remains omitted even if the proof succeeds. No LLM is
needed for this experiment; fixture responses do not establish real-model
quality or absence of hallucinations. The permissible result is: **the pinned
verifier established P1-P5 for the recorded abstract model under the stated
assumptions**. Tests provide finite evidence relating Python behavior to it;
they do not close the formal correspondence gap.

References: [Dafny contracts](https://dafny.org/latest/OnlineTutorial/guide),
[verification CLI and assumptions](https://dafny.org/latest/DafnyRef/DafnyRef.html).
