# G02 design

## Controlled comparison

The only intervention is review queue order. Both runs use 24 tasks arriving
every two logical ticks, four execution slots, eight ticks for initial execution,
one reviewer taking six ticks per review, and no admission limit. Task IDs
3, 7, 11, 15, 19 and 23 require exactly one four-tick correction. These choices
are assumptions, fixed before observing the result. The second review accepts.
The first horizon is tick 60; the drain deadline is tick 500.

FIFO orders all ready review attempts by ready tick then task ID. The other
policy orders returning corrections first, then uses the same FIFO order within
each class. Review service cannot be interrupted. Execution is FIFO by request
tick then task ID in the same shared pool for initial work and corrections.

At each event tick: register arrivals; finish executions; finish the active
review; dispatch execution; dispatch review; record the state. All work ready
at a tick is eligible before the reviewer chooses. No service takes zero ticks.
Event IDs distinguish attempts. Requesting changes keeps the task unfinished;
only acceptance ends it.

## Evidence and limits

The model reports attempts, decisions, per-task waits and paired deltas, plus
state counts at the horizon and at drain/deadline. Metrics include arrival to
final acceptance, ready to first review, arrival to first review, and separate
turnaround summaries for corrected and first-pass tasks. A distribution is
reported only when its entire cohort is observed; missing observations remain
explicit. Percentiles use nearest rank. Work and reviewer time are reconciled
against the trace; corrections do not create additional tasks.

Pure calculation is independent of the gateway and workers. The existing
exclusive export writer can write the new experiment type under its own local
directory; the existing report reader remains restricted to Review Capacity.
Reports include model version, inputs, hashes and synthetic provenance. Existing
attempts cannot be overwritten. No provider, network or new permission is needed.

This model does not evaluate quality, reviewer fatigue, real error rates, repeat
corrections or production team performance. A finite batch cannot establish
starvation behavior under a continuing arrival stream.
