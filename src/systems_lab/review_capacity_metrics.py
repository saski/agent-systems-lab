"""Pure metrics computation for review capacity simulation.

Computes horizon and drain metrics from task and sample data without side effects.
"""

import math
from typing import Any


def compute_metrics(
    tasks: list[dict[str, Any]],
    samples: list[dict[str, Any]],
    horizon: int,
    execution_slots: int,
    deadline: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute horizon and drain metrics from simulation data.

    Args:
        tasks: List of task dicts with arrival_tick, decision_tick, etc.
        samples: List of sample dicts with tick, queued, executing, etc.
        horizon: Observation horizon tick.
        execution_slots: Number of execution slots in policy.
        deadline: Drain deadline tick.

    Returns:
        Tuple of (horizon_metrics, drain_metrics) dicts.
    """
    task_count = len(tasks)

    # Horizon metrics
    horizon_decided = sum(
        1 for t in tasks if t["decision_tick"] is not None and t["decision_tick"] <= horizon
    )
    horizon_pending = task_count - horizon_decided

    not_arrived = sum(1 for t in tasks if t["arrival_tick"] > horizon)

    # Oldest pending age: arrived, unfinished at horizon
    oldest_pending_age = None
    for t in tasks:
        if t["arrival_tick"] <= horizon:
            if t["decision_tick"] is None or t["decision_tick"] > horizon:
                age = horizon - t["arrival_tick"]
                if oldest_pending_age is None or age > oldest_pending_age:
                    oldest_pending_age = age

    # Decided cohort: tasks with actual decision <= horizon
    decided_tasks = [
        t for t in tasks if t["decision_tick"] is not None and t["decision_tick"] <= horizon
    ]

    horizon_latencies = [t["decision_tick"] - t["arrival_tick"] for t in decided_tasks]

    horizon_admission_waits = [
        t["admission_tick"] - t["arrival_tick"]
        for t in decided_tasks
        if t["admission_tick"] is not None
    ]

    horizon_review_waits = [
        t["review_start_tick"] - t["ready_tick"]
        for t in decided_tasks
        if t["review_start_tick"] is not None and t["ready_tick"] is not None
    ]

    # Queue peaks and means from samples <= horizon
    horizon_samples = [s for s in samples if s["tick"] <= horizon]

    queued_peak = max((s["queued"] for s in horizon_samples), default=0)
    awaiting_review_peak = max((s["awaiting_review"] for s in horizon_samples), default=0)
    wip_peak = max((s["wip"] for s in horizon_samples), default=0)

    queued_mean = _integrate_mean(horizon_samples, "queued", horizon)
    awaiting_review_mean = _integrate_mean(horizon_samples, "awaiting_review", horizon)
    wip_mean = _integrate_mean(horizon_samples, "wip", horizon)

    # Utilization: mean reviewing and mean executing / slots
    reviewer_utilization = _integrate_mean(horizon_samples, "reviewing", horizon)

    executing_mean = _integrate_mean(horizon_samples, "executing", horizon)
    execution_utilization = (
        None
        if horizon == 0 or execution_slots == 0 or executing_mean is None
        else executing_mean / execution_slots
    )

    # Throughput
    throughput = None if horizon == 0 else horizon_decided / horizon

    horizon_metrics = {
        "tick": horizon,
        "decided": horizon_decided,
        "pending": horizon_pending,
        "not_arrived": not_arrived,
        "oldest_pending_age": oldest_pending_age,
        "queue_peaks": {
            "queued": queued_peak,
            "awaiting_review": awaiting_review_peak,
            "wip": wip_peak,
        },
        "queue_means": {
            "queued": queued_mean,
            "awaiting_review": awaiting_review_mean,
            "wip": wip_mean,
        },
        "reviewer_utilization": reviewer_utilization,
        "execution_utilization": execution_utilization,
        "throughput": throughput,
        "latency": _percentile_stats(horizon_latencies),
        "admission_wait": _percentile_stats(horizon_admission_waits),
        "review_wait": _percentile_stats(horizon_review_waits),
    }

    # Drain metrics: use actual final tick from last sample
    final_tick = samples[-1]["tick"] if samples else 0

    drain_decided = sum(
        1 for t in tasks if t["decision_tick"] is not None and t["decision_tick"] <= final_tick
    )
    drain_pending = task_count - drain_decided
    drain_complete = drain_pending == 0

    drain_makespan = None
    last_decision_tick = None
    if drain_complete and task_count > 0:
        first_arrival = min(t["arrival_tick"] for t in tasks)
        last_decision_tick = max(
            t["decision_tick"] for t in tasks if t["decision_tick"] is not None
        )
        drain_makespan = last_decision_tick - first_arrival

    drain_end_tick = last_decision_tick if drain_complete else deadline

    # Drain distributions: actual decisions only
    decided_drain_tasks = [
        t for t in tasks if t["decision_tick"] is not None and t["decision_tick"] <= final_tick
    ]

    drain_latencies = [t["decision_tick"] - t["arrival_tick"] for t in decided_drain_tasks]

    drain_admission_waits = [
        t["admission_tick"] - t["arrival_tick"]
        for t in decided_drain_tasks
        if t["admission_tick"] is not None
    ]

    drain_review_waits = [
        t["review_start_tick"] - t["ready_tick"]
        for t in decided_drain_tasks
        if t["review_start_tick"] is not None and t["ready_tick"] is not None
    ]

    drain_metrics = {
        "complete": drain_complete,
        "decided": drain_decided,
        "pending": drain_pending,
        "makespan": drain_makespan,
        "end_tick": drain_end_tick,
        "latency": _percentile_stats(drain_latencies),
        "admission_wait": _percentile_stats(drain_admission_waits),
        "review_wait": _percentile_stats(drain_review_waits),
    }

    return horizon_metrics, drain_metrics


def _integrate_mean(samples: list[dict[str, Any]], field: str, horizon: int) -> float | None:
    """Integrate field over [0, horizon] using right-continuous samples."""
    if horizon == 0:
        return None
    if not samples:
        return None

    total = 0.0
    for i in range(len(samples) - 1):
        value = samples[i][field]
        next_tick = samples[i + 1]["tick"]
        current_tick = samples[i]["tick"]
        duration = min(next_tick, horizon) - current_tick
        total += value * duration

    # Last sample to horizon
    last = samples[-1]
    if last["tick"] < horizon:
        total += last[field] * (horizon - last["tick"])

    return total / horizon


def _percentile_stats(values: list[int]) -> dict[str, Any]:
    """Compute count, p50, p95 using nearest-rank, null with 0 count."""
    count = len(values)
    if count == 0:
        return {"count": 0, "p50": None, "p95": None}

    sorted_vals = sorted(values)

    def nearest_rank(p: float) -> int:
        rank = int(math.ceil(p * count))
        return sorted_vals[rank - 1]

    return {
        "count": count,
        "p50": nearest_rank(0.5),
        "p95": nearest_rank(0.95),
    }
