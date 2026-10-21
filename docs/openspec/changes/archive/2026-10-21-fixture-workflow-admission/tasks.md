# Implementation tasks

Implemented and verified on 21 October 2026 after explicit user authorization.
All acceptance tasks are complete; see `verification.md` for evidence and limits.

## First Vertical Slice: Two Fixture Tasks, WIP One

- [x] Start with one failing behavior test: advance two queued fixture tasks;
      the first reaches `awaiting_review`, retains WIP one and the second has
      no canonical run or worker. Repeating advance changes none of those facts.
- [x] Add bounded durable batch/item state, transactional reservation and
      idempotent run binding; use stable item identities and FIFO order.
- [x] Add operator-only batch create/advance/status operations and CLI integration;
      reject viewer/worker writes and preserve existing single-run commands.
- [x] Reuse separate run/checkpoint identities and the existing fixture graph;
      prove that worker completion and human interrupt do not release WIP.
- [x] Exercise manual accept and reject with the exact digest; show that a stale
      digest, unauthorized request or direct checkpoint resume cannot free WIP.
- [x] Reconcile a terminal outcome and admit task two exactly once, preserving
      the first run's artifacts and completed-worker count.

## Ownership and Recovery

- [x] Test competing owners through independent database connections and actual
      coordinator processes; cover the graph-launch boundary and hold the local
      process lock until invocation exits. A binding retry returns the same run
      without dispatch; uncertain prior launch remains blocked.
- [x] Restart at human review without repeating specialists; block ambiguous
      in-flight recovery instead of automatically executing or re-admitting work.
- [x] Test revocation, worker failure, gateway outage and owner takeover;
      retain capacity until canonical outcomes and worker cleanup are confirmed.

## Evidence and Closure

- [x] Run an isolated real-process fixture demonstration, record all identities
      and reconcile queue, worker and canonical outcome counts; label provenance.
- [x] Document the hypothesis, boundary, observations, recovery limits and manual
      operator steps; update the roadmap without changing numerical claims.
- [x] Run `make check`, `make spec-check` and `git diff --check`; archive only
      after the implementation and evidence meet this proposal.
