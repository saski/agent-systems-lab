# Dafny call-budget learning experiment

Status: proposed on 20 October 2026; no Dafny implementation or proof exists yet.

## Why

Learn what a formal proof can establish beyond the gateway's example-based
tests. The question is whether any sequence of requests can spend more calls
than one grant allows.

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
- Introduce one deliberately incorrect `<=` guard in an isolated faulty
  variant. The verifier should reject it at the exhausted limit, showing that
  the check can catch the specific off-by-one error. Keep the contract unchanged.
- Provide an explicit, opt-in verification command and a short learning guide
  with reproducible evidence and a precise guarantee statement.

## Hypothesis, Variables and Observations

Hypothesis: a property that holds in the initial state and remains true after
every modeled authorization step can establish the per-grant budget bound for
all finite request sequences in this model. Python tests provide evidence only
for the cases they execute.

Keep the contract, initial state and toolchain fixed. Vary request eligibility,
call limit, request sequence and deactivation position; in the faulty variant,
change only `<` to `<=`. At the boundary `used = limit = 1`, the grant has no
calls left, so this faulty guard would incorrectly allow one more. Record
verification diagnostics, source hashes, commands, tool versions and test outcomes.
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
