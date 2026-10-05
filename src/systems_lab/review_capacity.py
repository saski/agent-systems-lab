"""Review capacity simulation model.

Event-driven simulation of task admission, execution, review, and decision flow.
"""

import hashlib
import json
from collections import deque
from typing import Any

from systems_lab.review_capacity_metrics import compute_metrics


def simulate(inputs: Any) -> dict[str, Any]:
    """Run simulation for all policies and return report."""
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be a dict")
    validated = _validate_inputs(inputs)
    scenario_hash = _hash_scenario(validated)

    policies_output = []
    for policy_cfg in validated["policies"]:
        policy_result = _simulate_policy(validated, policy_cfg, scenario_hash)
        policies_output.append(policy_result)

    return {
        "model_version": "review-capacity-v1",
        "inputs": _snapshot_inputs(validated),
        "scenario_sha256": scenario_hash,
        "provenance": "synthetic_event_time_model",
        "policies": policies_output,
        "limitations": [
            "synthetic",
            "accepts_all",
            "uniform_services",
            "no_quality",
            "no_rework",
            "no_error",
            "Logical ticks, not wall time.",
        ],
    }


def _validate_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Validate and return clean input dict."""
    required = {
        "model_version",
        "task_count",
        "arrival_interval",
        "execution_ticks",
        "review_ticks",
        "observation_horizon",
        "drain_deadline",
        "policies",
    }
    actual = set(inputs.keys())
    if actual != required:
        raise ValueError(f"Expected keys {required}, got {actual}")

    v = inputs["model_version"]
    if v != "review-capacity-v1":
        raise ValueError(f"model_version must be 'review-capacity-v1', got {v}")

    tc = inputs["task_count"]
    _check_int(tc, "task_count", 1, 100)

    ai = inputs["arrival_interval"]
    _check_int(ai, "arrival_interval", 0, 10000)

    last_arrival = (tc - 1) * ai
    if last_arrival > 10000:
        raise ValueError(f"last scheduled arrival {last_arrival} exceeds 10000")

    et = inputs["execution_ticks"]
    _check_int(et, "execution_ticks", 1, 100)

    rt = inputs["review_ticks"]
    _check_int(rt, "review_ticks", 1, 100)

    oh = inputs["observation_horizon"]
    _check_int(oh, "observation_horizon", 0, 50000)

    dd = inputs["drain_deadline"]
    _check_int(dd, "drain_deadline", 0, 50000)

    if dd < oh:
        raise ValueError(f"drain_deadline {dd} < observation_horizon {oh}")

    policies = inputs["policies"]
    if not isinstance(policies, list):
        raise ValueError("policies must be a list")
    if not (1 <= len(policies) <= 8):
        raise ValueError(f"policies length must be 1-8, got {len(policies)}")

    names = set()
    for pol in policies:
        if not isinstance(pol, dict):
            raise ValueError("each policy must be a dict")
        if set(pol.keys()) != {"name", "execution_slots", "wip_limit"}:
            raise ValueError("policy keys must be name, execution_slots, wip_limit")

        name = pol["name"]
        if not isinstance(name, str):
            raise ValueError("policy name must be string")
        if not (1 <= len(name) <= 64):
            raise ValueError(f"policy name length must be 1-64, got {len(name)}")
        if name in names:
            raise ValueError(f"duplicate policy name: {name}")
        names.add(name)

        slots = pol["execution_slots"]
        _check_int(slots, "execution_slots", 1, 8)

        wip = pol["wip_limit"]
        if wip is not None:
            _check_int(wip, "wip_limit", 1, 100)

    return inputs


def _check_int(val: Any, name: str, min_val: int, max_val: int) -> None:
    """Validate integer in range, reject bool/float."""
    if isinstance(val, bool):
        raise ValueError(f"{name} must be int, not bool")
    if not isinstance(val, int):
        raise ValueError(f"{name} must be int")
    if not (min_val <= val <= max_val):
        raise ValueError(f"{name} must be in [{min_val}, {max_val}], got {val}")


def _hash_scenario(inputs: dict[str, Any]) -> str:
    """Compute deterministic SHA256 of scenario params."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _snapshot_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Deep copy of inputs."""
    return json.loads(json.dumps(inputs))


def _simulate_policy(
    scenario: dict[str, Any], policy: dict[str, Any], scenario_hash: str
) -> dict[str, Any]:
    """Simulate single policy and return results."""
    task_count = scenario["task_count"]
    arrival_interval = scenario["arrival_interval"]
    exec_ticks = scenario["execution_ticks"]
    review_ticks = scenario["review_ticks"]
    horizon = scenario["observation_horizon"]
    deadline = scenario["drain_deadline"]

    policy_name = policy["name"]
    execution_slots = policy["execution_slots"]
    wip_limit = policy["wip_limit"]

    # Task state: arrival_tick, admission_tick, ready_tick, review_start_tick, decision_tick
    tasks = [
        {
            "task_id": i,
            "arrival_tick": i * arrival_interval,
            "admission_tick": None,
            "ready_tick": None,
            "review_start_tick": None,
            "decision_tick": None,
        }
        for i in range(task_count)
    ]

    # Queues and services
    admission_queue = deque()  # task indices waiting admission
    executing = {}  # task_id -> completion_tick
    awaiting_review = deque()  # task indices awaiting review
    reviewing = {}  # task_id -> completion_tick

    # Event tracking
    samples = []
    events = []
    event_counter = [0]

    def make_event(task_id: int, transition: str, tick: int) -> dict[str, Any]:
        event_counter[0] += 1
        # Normalize internal transition names to public contract
        transition_map = {
            "arrival": "arrived",
            "admission": "admitted",
            "execution_start": "ready",
            "ready": "ready",
            "review_start": "review_started",
            "decision": "decided",
        }
        canonical_transition = transition_map.get(transition, transition)
        return {
            "event_id": f"{scenario_hash}:{policy_name}:{task_id}:{canonical_transition}",
            "task_id": task_id,
            "transition": canonical_transition,
            "tick": tick,
        }

    def record_sample(tick: int) -> None:
        arrived = sum(1 for t in tasks if t["arrival_tick"] <= tick)
        queued = len(admission_queue)
        executing_count = len(executing)
        awaiting_count = len(awaiting_review)
        reviewing_count = len(reviewing)
        decided = sum(
            1 for t in tasks if t["decision_tick"] is not None and t["decision_tick"] <= tick
        )
        wip = executing_count + awaiting_count + reviewing_count

        samples.append(
            {
                "tick": tick,
                "arrived": arrived,
                "queued": queued,
                "executing": executing_count,
                "awaiting_review": awaiting_count,
                "reviewing": reviewing_count,
                "decided": decided,
                "wip": wip,
            }
        )

    # Simulation loop
    tick = 0

    while True:
        # Complete services
        completed_exec = [tid for tid, end in executing.items() if end == tick]
        for tid in completed_exec:
            del executing[tid]
            tasks[tid]["ready_tick"] = tick
            awaiting_review.append(tid)
            events.append(make_event(tid, "ready", tick))

        completed_review = [tid for tid, end in reviewing.items() if end == tick]
        for tid in completed_review:
            del reviewing[tid]
            tasks[tid]["decision_tick"] = tick
            events.append(make_event(tid, "decision", tick))

        # Register arrivals
        for tid, task in enumerate(tasks):
            if task["arrival_tick"] == tick:
                admission_queue.append(tid)
                events.append(make_event(tid, "arrival", tick))

        # Queue completed execution by ready tick, then task id
        awaiting_sorted = sorted(awaiting_review, key=lambda tid: (tasks[tid]["ready_tick"], tid))
        awaiting_review.clear()
        awaiting_review.extend(awaiting_sorted)

        # Start reviews
        while awaiting_review and len(reviewing) == 0:
            tid = awaiting_review.popleft()
            tasks[tid]["review_start_tick"] = tick
            reviewing[tid] = tick + review_ticks
            events.append(make_event(tid, "review_start", tick))

        # Admit and start execution atomically
        while admission_queue:
            current_wip = len(executing) + len(awaiting_review) + len(reviewing)
            if wip_limit is not None and current_wip >= wip_limit:
                break
            if len(executing) >= execution_slots:
                break

            tid = admission_queue.popleft()
            tasks[tid]["admission_tick"] = tick
            executing[tid] = tick + exec_ticks
            events.append(make_event(tid, "admission", tick))

        # Record sample
        record_sample(tick)

        # Determine next event
        all_decided = all(t["decision_tick"] is not None for t in tasks)

        if tick == deadline:
            break

        if all_decided:
            if tick >= horizon:
                break
            else:
                # Add horizon sample if needed
                if tick < horizon:
                    record_sample(horizon)
                break

        # Find next event time
        next_events = []

        for end in executing.values():
            if end > tick:
                next_events.append(end)

        for end in reviewing.values():
            if end > tick:
                next_events.append(end)

        for task in tasks:
            if task["arrival_tick"] > tick:
                next_events.append(task["arrival_tick"])

        next_events.append(deadline)

        if horizon > tick:
            next_events.append(horizon)

        if next_events:
            tick = min(next_events)
        else:
            break

    # Compute horizon and drain metrics using helper
    horizon_metrics, drain_metrics = compute_metrics(
        tasks, samples, horizon, execution_slots, deadline
    )

    return {
        "name": policy_name,
        "execution_slots": execution_slots,
        "wip_limit": wip_limit,
        "tasks": tasks,
        "samples": samples,
        "events": events,
        "horizon": horizon_metrics,
        "drain": drain_metrics,
    }
