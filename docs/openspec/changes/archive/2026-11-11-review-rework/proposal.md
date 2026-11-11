# G02: review order when work returns for correction

## Why

Review Capacity accepts every task on its first review. It cannot show who waits
when a review requests changes. G02 adds a separate, local numerical experiment:
24 tasks, six fixed corrections, and one reviewer. Compare FIFO review with
priority for corrected tasks returning for review. Measure final acceptance and
the first-review delays paid by other tasks.

## What Changes

The slice includes a deterministic model, fixed scenario, paired per-task traces,
bounded inputs, exclusive hashed CLI exports, tests and a learning guide with
the observed results. It preserves the existing Review Capacity model and its
report API. There are no real models, workers, external writes or automatic
human approvals. Dashboard integration and public writing are outside this slice.
