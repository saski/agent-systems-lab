# Experiments and reading

This directory connects executable systems with questions from *Thinking in
Systems*. Keep the book's ideas, your interpretation, a model's assumptions,
and observed numerical results distinguishable. Do not copy substantial book text.

Create a named directory for a new experiment and use this outline:

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
summaries, and page references from your edition. Keep confidential or raw
operational data in ignored local storage.

Keep reusable coordination contracts, prompts and selected execution evidence
beside their experiment, as in the
[Review Capacity coordination recipes](review-capacity/coordination/README.md).
Expanded machine-specific contracts and complete logs belong in ignored
`.lab/coordination/<run-id>/`; shared launchers and routing policy belong in Arnesto.

The first [backlog feedback](backlog-feedback/README.md) experiment includes a
ready scenario. To compare delays, copy its JSON to an ignored local file,
change `observation_delay` only, and run:

```sh
uv run systems-lab run --scenario .lab/short-delay.json
```

Compare the generated `simulation.json` files, including all parameters and
time-series observations. A successful agent run is evidence about the workflow;
it does not establish that the simulated system describes a real organization.
