# Backlog feedback experiment

This experiment follows a task backlog over time. The backlog is a stock: the
number of unfinished tasks carried from one step to the next. New tasks arrive
each step, while a staffing controller adjusts how many tasks can be processed
after observing the backlog. The model explores feedback, delays and capacity
limits discussed in Donella Meadows's *Thinking in Systems*. Its numbers are
for teaching; they do not reproduce examples or results from the book.

## Hypothesis and boundary

**Hypothesis:** when the controller reacts to older backlog observations, the
same gain can produce a larger backlog peak and more total capacity movement
than when it sees the current backlog.

The model includes one backlog, constant task arrivals, a processing capacity
with lower and upper bounds, and one controller that reacts to backlog. It
leaves out task priorities, partial work, worker ramp-up, turnover, random
arrivals, and effects from quality or deadlines. A step stands for an
unspecified planning interval; both task counts and capacity are measured for
that interval.

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

Backlog and arrivals count tasks. Capacity and completed work count tasks per
step, and the gain measures capacity change per task of backlog error. The
model uses no random sampling, so the same scenario always produces the same
result. If the observation delay lasts as long as the experiment, the
controller sees only the initial backlog. That is a deliberate scenario in
which its information stays fixed, not an invalid numeric input. The gateway
limits each run to 1,000 steps and rejects non-finite computations.

Model version: `backlog-feedback-v1`. The initial capacity is the starting
reference for measuring capacity movement; the controller chooses the first
effective capacity before processing any tasks.

## Observations

With the supplied parameters, the model produces these results:

| Observation delay | Final backlog | Maximum backlog | Completed tasks | Total capacity movement |
| ---: | ---: | ---: | ---: | ---: |
| 0 steps | 8.00 | 10.00 | 362.00 | 7.60 |
| 4 steps | 10.13 | 12.76 | 359.87 | 16.81 |

These numbers describe this deterministic simulation. With the longer delay,
the backlog peaks higher, capacity moves more, and fewer tasks are completed
than with no delay. The result does not show that delay always has this effect.
It depends on arrivals, initial conditions, gain, capacity bounds and run
length. The model also has no empirically calibrated relationship between
staffing and real-world throughput.

The JSON result includes the parameters, the backlog seen by the controller and
the flows at each step. It also reports final and maximum backlog, total
completions and cumulative absolute capacity change.

## Reading prompts

- Which part of this model is a stock, and which quantities change that stock?
- What would you expect to change if arrivals rose while maximum capacity stayed fixed?
- How would you test whether a longer delay or a larger gain is responsible for a larger backlog swing?
