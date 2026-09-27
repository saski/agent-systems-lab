# Backlog feedback experiment

This experiment models a task backlog as a stock. New tasks arrive each step,
and a staffing controller changes the processing capacity in response to an
observed backlog. It is inspired by feedback, delays, and capacity limits
discussed in Donella Meadows's *Thinking in Systems*. The numbers here are a
small teaching model; they do not reproduce examples or results from the book.

## Hypothesis and boundary

**Hypothesis:** when the controller reacts to older backlog observations, the
same gain can produce a larger backlog peak and more total capacity movement
than when it sees the current backlog.

The model boundary includes one backlog stock, constant task arrivals, bounded
processing capacity, and one backlog-based controller. It excludes task
priorities, partial work, worker ramp-up, turnover, stochastic arrivals, and
other feedback from quality or deadlines. One time step represents one
unspecified planning interval; task counts and capacity use the same interval.

## Variables and update order

The supplied [`scenario.json`](scenario.json) uses 36 steps, 10 initial tasks,
10 arriving tasks per step, a target backlog of 8 tasks, and capacity bounded
from 0 to 20 tasks per step. The controller starts with capacity 4; its
baseline is 10 tasks per step and its gain is 0.4 capacity units per task of
observed backlog error. Change `observation_delay` from 4 to 0 for the short
delay comparison, keeping all other values fixed.

Each step follows this order:

1. Read the beginning backlog from `observation_delay` steps earlier. Until
   that history exists, use the initial backlog.
2. Set capacity to `base_capacity + adjustment_gain * (observed_backlog -
   target_backlog)`, clamped to the configured minimum and maximum.
3. Add arrivals to the starting backlog, then complete the smaller of
   available tasks and current capacity.
4. Record the remaining backlog and retain it for future observations.

Backlog and arrivals are tasks. Capacity and completed work are tasks per
step. The gain has units of capacity per task. There is no random sampling, so
the same scenario always produces the same result. An observation delay as long
as the experiment horizon means the controller sees only the initial backlog;
this is a deliberate frozen-information scenario, not an invalid numeric input.
The gateway limits each run to 1,000 steps and rejects non-finite computations.

Model version: `backlog-feedback-v1`. The initial capacity is the starting
reference for measuring capacity movement; the controller chooses the first
effective capacity before processing any tasks.

## Observations

For the supplied parameters, the model produces the following results:

| Observation delay | Final backlog | Maximum backlog | Completed tasks | Total capacity movement |
| ---: | ---: | ---: | ---: | ---: |
| 0 steps | 8.00 | 10.00 | 362.00 | 7.60 |
| 4 steps | 10.13 | 12.76 | 359.87 | 16.81 |

These are numerical facts about this particular deterministic simulation. They
show a higher peak backlog, more capacity movement, and fewer completed tasks
with the longer delay in this run. They do not establish that delay always has this effect: the outcome
depends on the arrivals, initial conditions, gain, capacity bounds, and run
length. The model also has no empirically calibrated relationship between
staffing and real-world throughput.

The result includes the parameters, each step's observed backlog and flows,
and summary metrics for final and maximum backlog, total completions, and
cumulative absolute capacity change. The result can be serialized as JSON.

## Reading prompts

- Which part of this model is a stock, and which quantities change that stock?
- What would you expect to change if arrivals rose while maximum capacity stayed fixed?
- How would you test whether a longer delay or a larger gain is responsible for a larger backlog swing?
