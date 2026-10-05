# Review Capacity coordination recipes

Captured on 2026-10-05 while implementation was still in progress. These files
preserve selected implementation instructions and coordinator receipts; they do
not establish that the numerical model, exports or dashboard are complete.

## What belongs in Git

- `contracts/` contains six selected task templates. The `requirement` field is
  the task prompt, including its original public source context where supplied.
- `prompts/worker-system.txt` preserves the worker role instruction.
- `evidence/worker-results.json` records outcomes, changed files and reported
  input usage, including failures. It omits full conversation streams.
- `evidence/manifest.json` records source and published hashes and the
  normalization applied to the selected recipes.

The original contracts, JSONL streams and temporary client configuration remain
under the implementation checkout's ignored `.lab/coordination/<run-id>/`.
Historical logs were not rewritten. Credentials, databases and full raw logs
must not be copied into this versioned directory.

## Reuse a recipe

The contracts are templates, not executable launch commands. Replace
`<WORKTREE>` with an absolute, non-sensitive Git worktree and `<RUN_ID>` with a
new run identifier, including any occurrences inside `requirement`. Write the
expanded contract into that worktree's `.lab/coordination/<run-id>/`.

Review the prompt, allowed files, source revision, model and validation command
before launching. Some prompts include a historical source snapshot and require
adaptation to the current code. Never replay an old fix blindly.

Use Arnesto's `free-agent-execution` skill for the admitted launcher and routing
policy. The Kiro model identifiers recorded here were used with an operator's
confirmation of Kiro Free; that is not universal evidence that those models are
free or admitted in another account. The existing canonical adapter does not
admit those identifiers. Do not change provider, purchase credits or introduce
a paid fallback to replay these templates.

The provisional launcher and rejected routing candidate are retained as a
reference in [Arnesto](https://github.com/saski/arnesto), under
`docs/free-worker-coordination/`.
That reference is not an installed replacement for the canonical adapter.

## What the receipts establish

`returned_for_review` means the worker returned within its recorded file scope;
it does not mean tests passed or the coordinator accepted the change. A failed
worker may still have changed files. Separate test evidence and final review
remain necessary.

The captured receipts include a no-change response rejected by the coordinator
and an input-limit failure reporting 60,453 input tokens. Input usage is exposed
after a provider call completes, so a 50,000-token guard can detect an overrun
without preventing that call. Report the failed status and review any changes.

Both early Hermes test attempts spent their bounded iterations reading and
returned before writing a file. A constrained task needs exact paths, sufficient
context and a small deliverable; a persuasive final response is not execution
evidence. These observations concern these attempts, not a general comparison
of Hermes, OpenCode or model quality.

Hashes help detect changed artifacts relative to a trusted reference. They do
not make local files or Git history immutable, and they do not guarantee that an
LLM will reproduce the same output.
