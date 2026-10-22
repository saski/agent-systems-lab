# Experiments and reading

These experiments use runnable models to explore questions from *Thinking in
Systems*. Keep the book's ideas separate from your interpretation, the model's
assumptions and the results it produces. Do not copy substantial book text.

For each new experiment, create a named directory and record:

1. **Question:** What do you want to understand or change?
2. **Boundary:** Which actors, stocks, flows, resources, and decisions are included?
3. **Hypothesis:** What behavior do you predict, under what assumptions?
4. **Model:** Define units, update order, feedback loops, delays, and constraints.
5. **Scenario:** Record every input and the version of the model being used.
6. **Intervention:** Change one factor or explain why several must change together.
7. **Observations:** Preserve outputs, failures, budgets, and intervention events.
8. **Interpretation:** Explain what the evidence supports and what remains unknown.
9. **Next experiment:** Identify the smallest change that could disprove your explanation.

Use `reading-notes.md` inside an experiment for personal questions, your own
summaries and page references from your edition. Keep confidential or raw
operational data in ignored local storage.

Keep reusable coordination contracts, prompts and selected execution evidence
beside the experiment they support. The
[Review Capacity coordination recipes](review-capacity/coordination/README.md)
page shows one example. Expanded machine-specific contracts and complete logs
belong in ignored
`.lab/coordination/<run-id>/`; shared launchers and routing policy belong in Arnesto.

The [backlog feedback](backlog-feedback/README.md) experiment includes a ready
scenario. To see how observation delay changes the backlog, copy its JSON to an
ignored local file, change only `observation_delay`, and run:

```sh
uv run systems-lab run --scenario .lab/short-delay.json
```

Compare the generated `simulation.json` files, including their parameters and
observations at each time step. A successful agent run provides evidence about
the steps it reached and the workflow controls it exercised. It does not show
that the model describes a real organization.

The completed [Review Capacity v0.2 experiment](review-capacity/README.md)
compares parallel execution with one synthetic reviewer, then tests how an
admitted-work limit changes where unfinished tasks wait. Its two-queue diagram,
fixed-horizon comparison and full-drain curves explain the results; the
standalone learning guide and local dashboard's Experiments view let you replay
individual task states. These are saved numerical results, separate from the
history of actual agent workflows.

The [fixture-workflow admission experiment](fixture-workflow-admission/README.md)
tests whether an actual workflow keeps its WIP place while waiting for human
review. It runs two fixed tasks with one admitted place. An operator decides
each task, and recovery leaves the place occupied when the outcome is uncertain.
This evidence comes from workflow processes, not the numerical model.
