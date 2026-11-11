"""Paired numerical review orders with fixed correction needs, in logical ticks."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from math import ceil
from typing import Any


@dataclass
class Attempt:
    number: int
    requested_tick: int
    execution_start_tick: int | None = None
    ready_tick: int | None = None
    review_start_tick: int | None = None
    review_end_tick: int | None = None
    decision: str | None = None


@dataclass
class Task:
    task_id: int
    arrival_tick: int
    needs_correction: bool
    state: str = "not_arrived"
    accepted_tick: int | None = None
    attempts: list[Attempt] = field(default_factory=list)


def simulate(inputs: Any) -> dict[str, Any]:
    """Compare both orders over the same bounded workload without runtime actions."""
    _validate(inputs)
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False)
    scenario = json.loads(canonical)
    policies = [_run(scenario, name) for name in ("fifo", "corrections_first")]
    deltas = []
    for baseline, priority in zip(policies[0]["tasks"], policies[1]["tasks"], strict=True):
        deltas.append(
            {
                "task_id": baseline["task_id"],
                "needs_correction": baseline["needs_correction"],
                **{
                    f"{metric}_delta": _difference(priority[metric], baseline[metric])
                    for metric in ("turnaround", "first_review_wait", "time_to_first_review")
                },
            }
        )
    return {
        "model_version": "review-rework-v1",
        "provenance": "synthetic_event_time_model",
        "inputs": scenario,
        "scenario_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "policies": policies,
        "comparison": {"delta_direction": "corrections_first_minus_fifo", "tasks": deltas},
        "limitations": [
            "Logical ticks, not wall time.",
            "Fixed correction needs; no measured quality or error rate.",
            "Every correction succeeds on its second review.",
            "Uniform service times, one non-preemptive reviewer, no fatigue.",
            "Finite workload; cannot establish starvation under continuous arrivals.",
            "No agents, model calls, human decisions or external actions.",
        ],
    }


def _validate(inputs: Any) -> None:
    bounds = {
        "task_count": (1, 100),
        "arrival_interval": (0, 10000),
        "execution_slots": (1, 8),
        "execution_ticks": (1, 100),
        "review_ticks": (1, 100),
        "correction_ticks": (1, 100),
        "observation_horizon": (0, 10000),
        "drain_deadline": (0, 50000),
    }
    expected = set(bounds) | {"model_version", "correction_task_ids"}
    if not isinstance(inputs, dict) or set(inputs) != expected:
        raise ValueError(f"Expected exactly these scenario keys: {sorted(expected)}")
    if inputs["model_version"] != "review-rework-v1":
        raise ValueError("model_version must be review-rework-v1")
    for name, (lower, upper) in bounds.items():
        value = inputs[name]
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError(f"{name} must be an integer in [{lower}, {upper}]")
    if (inputs["task_count"] - 1) * inputs["arrival_interval"] > 10000:
        raise ValueError("last arrival must be at or before tick 10000")
    if inputs["drain_deadline"] < inputs["observation_horizon"]:
        raise ValueError("drain_deadline must be at or after observation_horizon")
    corrections = inputs["correction_task_ids"]
    if not isinstance(corrections, list) or any(
        type(task_id) is not int or not 0 <= task_id < inputs["task_count"]
        for task_id in corrections
    ):
        raise ValueError("correction_task_ids must be a list of scheduled integer task IDs")
    if corrections != sorted(set(corrections)):
        raise ValueError("correction_task_ids must be sorted and unique")


def _difference(end: int | None, start: int | None) -> int | None:
    return None if end is None or start is None else end - start


def _distribution(values: list[int | None]) -> dict[str, Any]:
    observed = sorted(value for value in values if value is not None)
    complete = bool(values) and len(observed) == len(values)
    return {
        "cohort_size": len(values),
        "observed": len(observed),
        "pending": len(values) - len(observed),
        "mean": sum(observed) / len(observed) if complete else None,
        "p50": observed[ceil(0.5 * len(observed)) - 1] if complete else None,
        "p95": observed[ceil(0.95 * len(observed)) - 1] if complete else None,
        "max": observed[-1] if complete else None,
    }


def _run(scenario: dict[str, Any], name: str) -> dict[str, Any]:
    tasks = [
        Task(i, i * scenario["arrival_interval"], i in scenario["correction_task_ids"])
        for i in range(scenario["task_count"])
    ]
    executing: dict[int, int] = {}
    reviewing: tuple[int, int] | None = None
    events: list[dict[str, Any]] = []
    samples: list[dict[str, int]] = []
    horizon: dict[str, int] | None = None
    drain: dict[str, Any] | None = None
    tick = 0

    def record(task: Task, transition: str) -> None:
        attempt = task.attempts[-1].number
        events.append(
            {
                "event_id": f"{task.task_id}:{attempt}:{transition}",
                "task_id": task.task_id,
                "attempt": attempt,
                "transition": transition,
                "tick": tick,
            }
        )

    def review_order(task: Task) -> tuple[bool, int, int]:
        attempt = task.attempts[-1]
        assert attempt.ready_tick is not None
        first_pass = name == "corrections_first" and attempt.number == 1
        return first_pass, attempt.ready_tick, task.task_id

    while horizon is None or drain is None:
        for task in tasks:
            if task.arrival_tick == tick:
                task.attempts.append(Attempt(1, tick))
                task.state = "waiting_execution"
                record(task, "arrived")

        for task_id in sorted(executing):
            if executing[task_id] == tick:
                task = tasks[task_id]
                task.attempts[-1].ready_tick = tick
                task.state = "awaiting_review"
                record(task, "ready_for_review")
                del executing[task_id]

        if reviewing is not None and reviewing[1] == tick:
            task = tasks[reviewing[0]]
            attempt = task.attempts[-1]
            attempt.review_end_tick = tick
            if task.needs_correction and attempt.number == 1:
                attempt.decision = "changes_requested"
                record(task, "changes_requested")
                task.attempts.append(Attempt(2, tick))
                task.state = "waiting_execution"
            else:
                attempt.decision = "accepted"
                task.accepted_tick = tick
                task.state = "accepted"
                record(task, "accepted")
            reviewing = None

        execution_queue = sorted(
            (task for task in tasks if task.state == "waiting_execution"),
            key=lambda task: (task.attempts[-1].requested_tick, task.task_id),
        )
        for task in execution_queue[: scenario["execution_slots"] - len(executing)]:
            attempt = task.attempts[-1]
            attempt.execution_start_tick = tick
            duration = scenario["execution_ticks" if attempt.number == 1 else "correction_ticks"]
            executing[task.task_id] = tick + duration
            task.state = "executing"
            record(task, "execution_started")

        review_queue = [task for task in tasks if task.state == "awaiting_review"]
        if reviewing is None and review_queue:
            task = min(review_queue, key=review_order)
            task.attempts[-1].review_start_tick = tick
            reviewing = task.task_id, tick + scenario["review_ticks"]
            task.state = "reviewing"
            record(task, "review_started")

        counts = {
            state: sum(task.state == state for task in tasks)
            for state in (
                "not_arrived",
                "waiting_execution",
                "executing",
                "awaiting_review",
                "reviewing",
                "accepted",
            )
        }
        snapshot = {
            "tick": tick,
            **counts,
            "arrived": len(tasks) - counts["not_arrived"],
            "unfinished": len(tasks) - counts["not_arrived"] - counts["accepted"],
        }
        samples.append(snapshot)
        if tick == scenario["observation_horizon"]:
            horizon = snapshot
        complete = counts["accepted"] == len(tasks)
        if drain is None and (complete or tick == scenario["drain_deadline"]):
            drain = snapshot | {"complete": complete}
        if horizon is not None and drain is not None:
            break
        upcoming = [scenario["observation_horizon"], scenario["drain_deadline"]]
        upcoming.extend(task.arrival_tick for task in tasks if task.state == "not_arrived")
        upcoming.extend(executing.values())
        if reviewing is not None:
            upcoming.append(reviewing[1])
        tick = min(future for future in upcoming if future > tick)

    assert drain is not None
    task_rows = []
    for task in tasks:
        first = task.attempts[0] if task.attempts else None
        task_rows.append(
            asdict(task)
            | {
                "turnaround": _difference(task.accepted_tick, task.arrival_tick),
                "first_review_wait": (
                    _difference(first.review_start_tick, first.ready_tick) if first else None
                ),
                "time_to_first_review": (
                    _difference(first.review_start_tick, task.arrival_tick) if first else None
                ),
            }
        )
    attempts = [attempt for task in tasks for attempt in task.attempts]
    return {
        "name": name,
        "tasks": task_rows,
        "events": events,
        "samples": samples,
        "horizon": horizon,
        "drain": drain,
        "metrics": {
            **{
                metric: _distribution([task[metric] for task in task_rows])
                for metric in ("turnaround", "first_review_wait", "time_to_first_review")
            },
            "turnaround_by_group": {
                group: _distribution(
                    [task["turnaround"] for task in task_rows if task["needs_correction"] == flag]
                )
                for group, flag in (("corrected", True), ("first_pass", False))
            },
            "review_rounds_completed": sum(a.review_end_tick is not None for a in attempts),
            "review_busy_ticks": sum(
                min(a.review_end_tick or drain["tick"], drain["tick"]) - a.review_start_tick
                for a in attempts
                if a.review_start_tick is not None
            ),
            "execution_busy_ticks": sum(
                min(a.ready_tick or drain["tick"], drain["tick"]) - a.execution_start_tick
                for a in attempts
                if a.execution_start_tick is not None
            ),
        },
    }
