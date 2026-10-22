# Review Capacity coordination recipes

These notes were captured on 2026-10-05, while implementation was still in
progress. They preserve some implementation instructions and coordinator
receipts from that point in time. They do not show that the numerical model,
exports or dashboard were complete.

## What belongs in Git

- `contracts/` contains six selected task templates. Each `requirement` field
  holds the task prompt and, where supplied, its original public source context.
- `prompts/worker-system.txt` preserves the worker role instruction.
- `evidence/worker-results.json` records outcomes, changed files and reported
  input usage, including failures. It omits full conversation streams.
- `evidence/manifest.json` records source and published hashes and the changes
  made while preparing the selected recipes for publication.

The original contracts, JSON Lines (JSONL) streams and temporary client
configuration remain in the implementation checkout's ignored
`.lab/coordination/<run-id>/` directory. Historical logs were left as recorded.
Credentials, databases and complete raw logs must not be copied into this
versioned directory.

## Reuse a recipe

The contracts describe tasks; they do not launch workers by themselves.
Replace `<WORKTREE>` with the absolute path to a non-sensitive Git worktree and
`<RUN_ID>` with a new run identifier. Replace every occurrence, including any
inside `requirement`, then write the expanded contract into that worktree's
`.lab/coordination/<run-id>/` directory.

Before launching, check the prompt, permitted files, source revision, model and
validation command. Some prompts refer to an older source snapshot, so their
instructions need to be adapted to the current code. An old fix cannot be
replayed safely without that review.

Use Arnesto's `free-agent-execution` skill to select an admitted launcher and
follow its routing policy. The recorded Kiro model identifiers were used after
an operator confirmed Kiro Free. That confirmation applies to that use; it does
not establish that the models are free or admitted for another account. The
current canonical adapter does not admit those identifiers. Replaying these
templates does not authorize changing providers, buying credits or adding a
paid fallback.

The provisional launcher and rejected routing candidate are retained as a
reference in [Arnesto](https://github.com/saski/arnesto), under
`docs/free-worker-coordination/`.
That reference is not an installed replacement for the canonical adapter.

## What the receipts establish

`returned_for_review` records that the worker returned within its stated file
scope. It does not tell us whether tests passed or whether the coordinator
accepted the change. Even a worker marked failed may have edited files, so check
the test evidence and review the changes separately.

The receipts include one no-change response that the coordinator rejected and
one input-limit failure that reported 60,453 input tokens. The provider reports
input usage only after a call completes. As a result, the 50,000-token guard
can identify an overrun after the call, but cannot stop that call from
happening. Record the failure and inspect any file changes.

In both early Hermes test attempts, the worker used its allotted iterations to
read and returned without writing a file. A constrained task still needs exact
paths, enough context and a small deliverable. A convincing final response by
itself does not show that the requested work was done. These notes describe
those attempts; they do not compare Hermes with OpenCode or measure either
model's quality.

Hashes can show that an artifact differs from a trusted reference. They cannot
prevent someone from changing local files or Git history, and they do not
guarantee that an LLM will produce the same output again.
