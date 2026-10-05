import hashlib
import json
from typing import Any

import pytest

from systems_lab.review_capacity import simulate


def base_input(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "model_version": "review-capacity-v1",
        "task_count": 2,
        "arrival_interval": 0,
        "execution_ticks": 2,
        "review_ticks": 3,
        "observation_horizon": 20,
        "drain_deadline": 50,
        "policies": [
            {
                "name": "fifo",
                "execution_slots": 1,
                "wip_limit": None,
            }
        ],
    }
    config.update(overrides)
    return config


def test_report_scenario_sha256_identity() -> None:
    inp = base_input()
    result = simulate(inp)
    canonical = json.dumps(
        result["inputs"],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert result["scenario_sha256"] == computed


def test_report_snapshot_checks() -> None:
    result = simulate(base_input())
    assert result["inputs"]["task_count"] == 2
    task_ids = {t["task_id"] for t in result["policies"][0]["tasks"]}
    assert task_ids == {0, 1}
    events = result["policies"][0]["events"]
    event_ids = {e["event_id"] for e in events}
    assert len(event_ids) == len(events)
    transitions = {e["transition"] for e in events}
    assert transitions == {
        "arrived",
        "admitted",
        "ready",
        "review_started",
        "decided",
    }
    completed_events = [
        e for e in events if e["task_id"] in {0, 1} and e["transition"] == "decided"
    ]
    assert len(completed_events) == 2
    total_events_for_completed = [e for e in events if e["task_id"] in {0, 1}]
    assert len(total_events_for_completed) == 10


def test_report_input_isolation() -> None:
    inp = base_input()
    result = simulate(inp)
    original_scenario = json.dumps(result["inputs"], sort_keys=True)
    inp["task_count"] = 999
    inp["policies"][0]["name"] = "mutated"
    assert json.dumps(result["inputs"], sort_keys=True) == original_scenario


def test_two_task_baseline() -> None:
    result = simulate(base_input())
    tasks = result["policies"][0]["tasks"]
    assert tasks[0]["admission_tick"] == 0
    assert tasks[1]["admission_tick"] == 2
    assert tasks[0]["ready_tick"] == 2
    assert tasks[1]["ready_tick"] == 4
    assert tasks[0]["review_start_tick"] == 2
    assert tasks[1]["review_start_tick"] == 5
    assert tasks[0]["decision_tick"] == 5
    assert tasks[1]["decision_tick"] == 8


def test_wip_limit_1_second_admission_5() -> None:
    result = simulate(
        base_input(
            policies=[
                {
                    "name": "fifo",
                    "execution_slots": 1,
                    "wip_limit": 1,
                }
            ]
        )
    )
    tasks = result["policies"][0]["tasks"]
    assert tasks[0]["decision_tick"] == 5
    assert tasks[1]["admission_tick"] == 5
    assert tasks[1]["decision_tick"] == 10


def test_invariants_and_capacities() -> None:
    result = simulate(
        base_input(
            task_count=5,
            execution_ticks=3,
            review_ticks=2,
            policies=[
                {
                    "name": "limited",
                    "execution_slots": 3,
                    "wip_limit": 2,
                }
            ],
        )
    )
    samples = result["policies"][0]["samples"]
    for sample in samples:
        arrived = sample["arrived"]
        queued = sample["queued"]
        executing = sample["executing"]
        awaiting_review = sample["awaiting_review"]
        reviewing = sample["reviewing"]
        decided = sample["decided"]
        wip = sample["wip"]
        assert queued + executing + awaiting_review + reviewing + decided == arrived
        assert executing + awaiting_review + reviewing == wip
        assert executing <= 3
        assert wip <= 2


def test_24_task_scenario_full_drain() -> None:
    result = simulate(
        base_input(
            task_count=24,
            arrival_interval=2,
            execution_ticks=8,
            review_ticks=6,
            observation_horizon=60,
            drain_deadline=500,
            policies=[
                {"name": "A", "execution_slots": 1, "wip_limit": None},
                {"name": "B", "execution_slots": 4, "wip_limit": None},
                {"name": "C", "execution_slots": 4, "wip_limit": 3},
            ],
        )
    )
    for policy in result["policies"]:
        if policy["name"] == "A":
            assert policy["horizon"]["decided"] == 6
            assert policy["horizon"]["pending"] == 18
        elif policy["name"] == "B":
            assert policy["horizon"]["decided"] == 8
            assert policy["horizon"]["pending"] == 16
        elif policy["name"] == "C":
            assert policy["horizon"]["decided"] == 8
            assert policy["horizon"]["pending"] == 16
        assert policy["drain"]["complete"] is True
        assert policy["drain"]["decided"] == 24
        assert policy["drain"]["pending"] == 0
        assert policy["drain"]["makespan"] <= 200


def test_horizon_zero_null_percentiles() -> None:
    result = simulate(base_input(observation_horizon=0, drain_deadline=100))
    horizon = result["policies"][0]["horizon"]
    drain = result["policies"][0]["drain"]
    assert horizon["decided"] == 0
    assert horizon["latency"]["count"] == 0
    assert horizon["latency"]["p50"] is None
    assert horizon["latency"]["p95"] is None
    assert drain["complete"] is True


def test_horizon_1_deadline_1_incomplete() -> None:
    result = simulate(base_input(task_count=2, observation_horizon=1, drain_deadline=1))
    drain = result["policies"][0]["drain"]
    tasks = result["policies"][0]["tasks"]
    assert drain["complete"] is False
    assert drain["decided"] == 0
    assert drain["pending"] == 2
    assert all(t["decision_tick"] is None for t in tasks)
    assert drain["latency"]["count"] == 0


def test_canonical_json_determinism() -> None:
    inp = base_input()
    r1 = json.dumps(simulate(inp), sort_keys=True)
    r2 = json.dumps(simulate(inp), sort_keys=True)
    assert r1 == r2
    result = simulate(inp)
    drain = result["policies"][0]["drain"]
    assert drain["complete"] is True
    assert drain["decided"] == 2
    assert drain["latency"]["count"] == 2
    assert drain["latency"]["p50"] == 5
    assert drain["latency"]["p95"] == 8


def test_horizon_metrics_simultaneous_tasks() -> None:
    result = simulate(
        base_input(
            task_count=2,
            arrival_interval=0,
            execution_ticks=2,
            review_ticks=3,
            observation_horizon=6,
            drain_deadline=50,
            policies=[{"name": "fifo", "execution_slots": 1, "wip_limit": None}],
        )
    )
    horizon = result["policies"][0]["horizon"]
    assert horizon["decided"] == 1
    assert horizon["pending"] == 1
    assert horizon["not_arrived"] == 0
    assert horizon["oldest_pending_age"] == 6
    assert horizon["latency"]["count"] == 1
    assert horizon["latency"]["p50"] == 5
    assert horizon["latency"]["p95"] == 5
    assert horizon["admission_wait"]["count"] == 1
    assert horizon["admission_wait"]["p50"] == 0
    assert horizon["admission_wait"]["p95"] == 0
    assert horizon["review_wait"]["count"] == 1
    assert horizon["review_wait"]["p50"] == 0
    assert horizon["review_wait"]["p95"] == 0
    assert horizon["reviewer_utilization"] == pytest.approx(4.0 / 6.0)
    assert horizon["execution_utilization"] == pytest.approx(4.0 / 6.0)
    assert horizon["queue_means"]["queued"] == pytest.approx(2.0 / 6.0)
    assert horizon["queue_means"]["awaiting_review"] == pytest.approx(1.0 / 6.0)
    assert horizon["queue_means"]["wip"] == pytest.approx(9.0 / 6.0)
    assert horizon["queue_peaks"]["queued"] == 1
    assert horizon["queue_peaks"]["awaiting_review"] == 1
    assert horizon["queue_peaks"]["wip"] == 2
    samples = result["policies"][0]["samples"]
    ticks = [s["tick"] for s in samples]
    assert 6 in ticks
    for i in range(1, len(ticks)):
        assert ticks[i] > ticks[i - 1]
    drain = result["policies"][0]["drain"]
    assert drain["makespan"] == 8


def test_late_arrivals_horizon_pending() -> None:
    result = simulate(
        base_input(
            task_count=2,
            arrival_interval=10,
            execution_ticks=2,
            review_ticks=3,
            observation_horizon=1,
            drain_deadline=30,
        )
    )
    horizon = result["policies"][0]["horizon"]
    assert horizon["pending"] == 2
    assert horizon["not_arrived"] == 1
    assert horizon["oldest_pending_age"] == 1
    assert horizon["latency"]["count"] == 0


def test_conservation_no_future_tasks_at_zero() -> None:
    result = simulate(
        base_input(
            task_count=2,
            arrival_interval=10,
            execution_ticks=2,
            review_ticks=3,
            observation_horizon=20,
            drain_deadline=50,
        )
    )
    samples = result["policies"][0]["samples"]
    sample_at_zero = next((s for s in samples if s["tick"] == 0), None)
    assert sample_at_zero is not None
    assert sample_at_zero["arrived"] == 1
    assert sample_at_zero["executing"] == 1
    assert sample_at_zero["queued"] == 0
    for sample in samples:
        arrived = sample["arrived"]
        queued = sample["queued"]
        executing = sample["executing"]
        awaiting_review = sample["awaiting_review"]
        reviewing = sample["reviewing"]
        decided = sample["decided"]
        assert queued + executing + awaiting_review + reviewing + decided == arrived


def test_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        simulate({"task_count": 5})
    with pytest.raises(ValueError):
        simulate(base_input(extra_field=True))
    with pytest.raises(ValueError):
        simulate(base_input(task_count=True))
    with pytest.raises(ValueError):
        simulate(base_input(execution_ticks=float("nan")))
    with pytest.raises(ValueError):
        simulate(base_input(review_ticks=float("inf")))
    with pytest.raises(ValueError):
        simulate(base_input(task_count=0))
    with pytest.raises(ValueError):
        simulate(base_input(task_count=101))
    with pytest.raises(ValueError):
        simulate(base_input(task_count=11, arrival_interval=1001))
    with pytest.raises(ValueError):
        simulate(base_input(observation_horizon=100, drain_deadline=50))
    with pytest.raises(ValueError):
        simulate(base_input(policies=[]))
    with pytest.raises(ValueError):
        simulate(
            base_input(
                policies=[
                    {"name": "p1", "execution_slots": 1, "wip_limit": None},
                    {"name": "p1", "execution_slots": 1, "wip_limit": None},
                ]
            )
        )
    with pytest.raises(ValueError):
        simulate(base_input(policies=[{"name": "", "execution_slots": 1, "wip_limit": None}]))
