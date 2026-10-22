# Evolution through experiments

The next capability should follow from something we want to learn. Start with
a question small enough to test, decide what stays constant and say what result
would count as an answer. Each experiment needs a hypothesis, observations and
acceptance criteria, with its costs and limitations recorded alongside them.

The completed work below gives us a starting point for further study. A proposed
runtime, live model or stronger isolation boundary still needs its own
experiment before we can claim it improves the system.

| Experiment | Question | Evidence to collect |
| --- | --- | --- |
| Bootstrap | Can three specialists complete a governed, restartable workflow? | Fixture loop, role denials, revocation, exact-artifact approval, container boundaries |
| Observation delay | How does stale information alter a balancing controller? | Backlog trajectories, capacity movement, saturation, sensitivity to gain |
| Review Capacity v0.2 — closed | Where does waiting move when execution capacity or admitted WIP changes? | Reconciled A/B/C numerical traces, bounded hashed exports, authenticated dashboard replay and [closure evidence](openspec/changes/archive/2026-10-20-review-capacity-experiment/verification.md) |
| Fixture-workflow admission — implemented | Does a workflow awaiting human review keep its admission place? | Two fixed tasks, one admitted at a time per batch, saved queue identities and decisions tied to the exact artifacts; recovery blocks new work when worker state is uncertain. See the [experiment](../experiments/fixture-workflow-admission/README.md) |
| Dafny call budget — proposed | Can any sequence of requests exceed one grant's call limit in a small formal model? | A proof of the model, a deliberately faulty variant that fails verification, and a comparison with Python tests; the [proposal](openspec/changes/dafny-call-budget/proposal.md) keeps this separate from a proof of the gateway |
| Fixed live-model route | Does a real model select tools and explain evidence reliably? | Useful nonempty output, schema validity, tool accuracy, cost, latency, adversarial cases |
| Runtime substitution | What changes when one specialist uses another runtime? | Same tasks, permissions and budgets; compare results and operational burden |
| Dynamic delegation | Can children receive only a subset of parent authority? | Verify who created each child, allow only permissions shared by parent and child, limit delegation depth, and revoke descendant access with the parent |
| Coding solution | Can a Builder modify a disposable project safely? | Sandboxed execution, scoped files, independent tests, diff-bound approval |
| Telemetry analysis | What feedback loops appear in agent behavior? | Build on the implemented event journal, OTLP export and activity dashboard; study retry feedback, queue growth, cost and interventions |
| Stronger isolation | What additional boundary is required for untrusted code? | Threat model, escape tests, microVM or equivalent evaluation |

Further reading may lead to questions about reinforcing loops, buffers,
competing goals, policy resistance, resilience or leverage points. Use the
question that stayed with you while reading, then build a small model you can
inspect. A chapter heading becomes useful here when we can say what we expect
to happen and what observation would make us reconsider.
