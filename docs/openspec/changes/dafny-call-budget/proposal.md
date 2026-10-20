# Dafny call-budget learning experiment

Status: proposed on 20 October 2026; no Dafny implementation or proof exists yet.

## Why

Learn what a formal proof adds to the gateway's existing example-based tests.
Use one concrete question: can a grant ever authorize more calls than its limit?

The current `Store.authorize` checks the run state, expiry, capability and call
budget, then increments the grant counter before dispatch. The budget is per
grant, shared by its model and tool calls. An authorization denial does not
consume budget; an authorized operation that later fails does.

## What Changes

- Add a standalone Dafny model of one grant, its authorization step and run
  deactivation, with a fixed positive call limit.
- Prove exact accounting, the budget bound and rejection after deactivation
  for arbitrary finite sequences of the modeled transitions.
- Compare those properties with current gateway tests and two additional
  accounting tests, without changing the production authorization behavior.
- Introduce one deliberately incorrect `<=` guard in an isolated negative
  variant. Keep the contract unchanged and demonstrate rejection at the limit.
- Provide an explicit, opt-in verification command and a short learning guide
  with reproducible evidence and a precise guarantee statement.

## Hypothesis, Variables and Observations

Hypothesis: an invariant over the authorization transition can establish a
per-grant budget bound for all finite modeled request sequences, while the
Python tests establish behavior only for their exercised cases.

Keep the contract, initial state and toolchain fixed. Vary request eligibility,
call limit, request sequence and deactivation position; for the negative variant
change only `<` to `<=`. Record verification diagnostics, source hashes, commands,
tool versions, test outcomes and the concrete boundary witness `used = limit = 1`.
No performance or model-quality comparison is intended.

## First Acceptance Slice and Non-Goals

Finish the model, negative control, two Python characterization tests and
evidence comparison. Keep all runtime evidence under ignored
`.lab/experiments/call-budget-dafny/`.

No gateway rewrite, generated-code integration, Lean exercise, provider calls,
external writes, new permissions, dashboard, distributed concurrency proof,
approval-digest proof or changes to other active proposals. A proof about this
model will not be described as formal verification of the Python gateway.

This proposal, its design, delta spec and tasks form the planning source for
this experiment. Implementation remains pending review of these artifacts.
