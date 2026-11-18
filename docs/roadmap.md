# Evolution through experiments

The next capability should follow from something we want to learn. Start with
a question small enough to test, decide what stays constant and say what result
would count as an answer. Each experiment needs a hypothesis, observations and
acceptance criteria, with its costs and limitations recorded alongside them.

The completed work below gives us a starting point for further study. A proposed
runtime, live model or stronger isolation boundary still needs its own
experiment before we can claim it improves the system.

## Evidence for a development increment

When a proposal gives agents a new way to develop software, use these questions
to define its acceptance criteria. Keep the evidence with the experiment so a
later operator can repeat the run and understand the decision.

| Property | Question the evidence should answer |
| --- | --- |
| Safety | Which files, tools and destinations can each role reach? Exercise a permitted action and an action outside the boundary. Record how the boundary was enforced. |
| Control | Who owns the next step and its retries? Identify the grant, budget and point of human intervention. Show what happens when the operator pauses, rejects or revokes work at the relevant boundary. |
| Visibility | Can an operator see the current stage and responsible role, where progress has stopped and who can act next? Distinguish work waiting for review from observations waiting for delivery. |
| Traceability | Can a reader follow one run from its task and policy version through the requested action, authorization and observed outcome to the exact artifact, verification result and human decision? Link those records by run ID and artifact digest. |
| Incrementality | What single change is under test? Keep the baseline, acceptance criterion, result and limitations together. Record whether the evidence supports keeping, revising or reversing the change. |

For example, a future coding experiment could compare one Builder with the
same Builder plus an independent Reviewer on a disposable repository. Keep
the task, starting revision, permission boundaries and total budget fixed.
Have the Reviewer reproduce a defect on the starting revision and run the
same test on the candidate. Keep both results with the diff digest and the
operator's decision. The current fixture workflow demonstrates gateway controls
and digest-bound review. Running a coding agent with write access belongs to
the proposed sandboxed coding experiment.

## Experiments

| Experiment | Question | Evidence to collect |
| --- | --- | --- |
| Bootstrap | Can three specialists complete a governed, restartable workflow? | Fixture loop, role denials, revocation, exact-artifact approval, container boundaries |
| Observation delay | How does stale information alter a balancing controller? | Backlog trajectories, capacity movement, saturation, sensitivity to gain |
| Review Capacity v0.2 — closed | Where does waiting move when execution capacity or admitted WIP changes? | Reconciled A/B/C numerical traces, bounded hashed exports, authenticated dashboard replay and [closure evidence](openspec/changes/archive/2026-10-20-review-capacity-experiment/verification.md) |
| G02: review with corrections — implemented | Who waits when returning corrections get priority over first reviews? | Paired 24-task traces with six fixed corrections, full-cohort and per-task latencies, conserved work, exclusive exports and a [comparison figure and learning guide](../experiments/review-rework/README.md) |
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
