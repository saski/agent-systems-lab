import hashlib
import json
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from systems_lab import cli
from systems_lab.review_capacity_exports import export_attempt, read_attempt
from systems_lab.review_rework import simulate


def scenario(**overrides: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "model_version": "review-rework-v1",
        "task_count": 4,
        "arrival_interval": 0,
        "execution_slots": 4,
        "execution_ticks": 1,
        "review_ticks": 2,
        "correction_ticks": 1,
        "correction_task_ids": [0],
        "observation_horizon": 3,
        "drain_deadline": 20,
    }
    return inputs | overrides


def test_returning_correction_moves_ahead_of_waiting_first_reviews() -> None:
    fifo, priority = simulate(scenario())["policies"]

    # At tick 5, task 0 has returned; tasks 2 and 3 still await their first review.
    assert [task["accepted_tick"] for task in fifo["tasks"]] == [11, 5, 7, 9]
    assert [task["accepted_tick"] for task in priority["tasks"]] == [7, 5, 9, 11]
    assert [task["first_review_wait"] for task in fifo["tasks"]] == [0, 2, 4, 6]
    assert [task["first_review_wait"] for task in priority["tasks"]] == [0, 2, 6, 8]

    for policy in (fifo, priority):
        # Requesting changes is not an acceptance or a departure from unfinished work.
        assert policy["horizon"]["accepted"] == 0
        assert policy["horizon"]["unfinished"] == 4
        assert policy["tasks"][0]["attempts"][0]["decision"] == "changes_requested"
        assert policy["tasks"][0]["attempts"][1]["decision"] == "accepted"
        assert policy["drain"]["complete"] is True
        assert policy["drain"]["tick"] == 11
        assert policy["metrics"]["review_rounds_completed"] == 5


def test_without_corrections_both_orders_are_identical() -> None:
    fifo, priority = simulate(scenario(correction_task_ids=[]))["policies"]
    assert fifo | {"name": "same"} == priority | {"name": "same"}


def test_return_ready_at_review_completion_is_eligible_without_preemption() -> None:
    fifo, priority = simulate(scenario(correction_ticks=2))["policies"]
    for policy in (fifo, priority):
        assert policy["tasks"][0]["attempts"][1]["ready_tick"] == 5
        first_review = policy["tasks"][1]["attempts"][0]
        assert (first_review["review_start_tick"], first_review["review_end_tick"]) == (3, 5)
    assert fifo["tasks"][2]["attempts"][0]["review_start_tick"] == 5
    assert priority["tasks"][0]["attempts"][1]["review_start_tick"] == 5


def test_correction_waits_for_the_shared_execution_pool_in_fifo_order() -> None:
    for policy in simulate(
        scenario(task_count=3, execution_slots=1, execution_ticks=3, review_ticks=1)
    )["policies"]:
        assert [t["attempts"][0]["execution_start_tick"] for t in policy["tasks"]] == [0, 3, 6]
        correction = policy["tasks"][0]["attempts"][1]
        assert (correction["requested_tick"], correction["execution_start_tick"]) == (4, 9)
        assert policy["tasks"][0]["accepted_tick"] == 11


@pytest.mark.parametrize("deadline", [0, 3, 5, 10])
def test_partial_drain_keeps_cohort_metrics_unavailable(deadline: int) -> None:
    for policy in simulate(scenario(observation_horizon=deadline, drain_deadline=deadline))[
        "policies"
    ]:
        assert policy["drain"]["complete"] is False
        assert policy["drain"]["tick"] == deadline
        metric = policy["metrics"]["turnaround"]
        accepted = sum(t["accepted_tick"] is not None for t in policy["tasks"])
        assert metric["observed"] == accepted
        assert metric["pending"] == 4 - accepted
        assert metric["mean"] is None
        assert metric["p95"] is None
        assert all(event["tick"] <= deadline for event in policy["events"])


def test_unscheduled_arrivals_are_separate_from_arrived_unfinished_work() -> None:
    for policy in simulate(scenario(arrival_interval=10, observation_horizon=3, drain_deadline=3))[
        "policies"
    ]:
        assert policy["drain"]["arrived"] == 1
        assert policy["drain"]["unfinished"] == 1
        assert policy["drain"]["not_arrived"] == 3
        assert policy["tasks"][1]["attempts"] == []
        assert policy["metrics"]["time_to_first_review"]["pending"] == 3


def test_horizon_after_full_drain_does_not_inflate_completion_or_service_time() -> None:
    for policy in simulate(scenario(observation_horizon=20))["policies"]:
        assert policy["horizon"]["accepted"] == 4
        assert policy["horizon"]["tick"] == 20
        assert policy["drain"]["tick"] == 11
        assert policy["metrics"]["review_busy_ticks"] == 10
        assert policy["metrics"]["execution_busy_ticks"] == 5


@pytest.mark.parametrize("slots,arrival,correction", list(product([1, 4], [0, 3], [1, 7])))
def test_trace_conserves_tasks_and_services(slots: int, arrival: int, correction: int) -> None:
    inputs = scenario(
        task_count=8,
        execution_slots=slots,
        arrival_interval=arrival,
        execution_ticks=3,
        correction_ticks=correction,
        correction_task_ids=[0, 3, 7],
        observation_horizon=25,
        drain_deadline=200,
    )
    for policy in simulate(inputs)["policies"]:
        assert policy["drain"]["complete"] is True
        assert policy["metrics"]["review_rounds_completed"] == 11
        assert policy["metrics"]["review_busy_ticks"] == 22
        assert policy["metrics"]["execution_busy_ticks"] == 24 + 3 * correction
        assert len({e["event_id"] for e in policy["events"]}) == len(policy["events"])
        for task in policy["tasks"]:
            assert len(task["attempts"]) == (2 if task["needs_correction"] else 1)
            for attempt in task["attempts"]:
                times = [
                    attempt[key]
                    for key in (
                        "requested_tick",
                        "execution_start_tick",
                        "ready_tick",
                        "review_start_tick",
                        "review_end_tick",
                    )
                ]
                assert times == sorted(times)
                assert attempt["review_end_tick"] - attempt["review_start_tick"] == 2
                duration = 3 if attempt["number"] == 1 else correction
                assert attempt["ready_tick"] - attempt["execution_start_tick"] == duration
            if task["needs_correction"]:
                assert (
                    task["attempts"][1]["requested_tick"] == task["attempts"][0]["review_end_tick"]
                )
            assert task["accepted_tick"] == task["attempts"][-1]["review_end_tick"]

        # Reconstruct each stock independently from the task intervals, including both visits.
        for sample in policy["samples"]:
            tick = sample["tick"]
            intervals = [a for t in policy["tasks"] for a in t["attempts"]]
            for state, start, end in (
                ("waiting_execution", "requested_tick", "execution_start_tick"),
                ("executing", "execution_start_tick", "ready_tick"),
                ("awaiting_review", "ready_tick", "review_start_tick"),
                ("reviewing", "review_start_tick", "review_end_tick"),
            ):
                assert sample[state] == sum(a[start] <= tick < a[end] for a in intervals)
            assert sample["accepted"] == sum(t["accepted_tick"] <= tick for t in policy["tasks"])
            assert sample["arrived"] == sum(t["arrival_tick"] <= tick for t in policy["tasks"])
            assert sample["unfinished"] + sample["accepted"] == sample["arrived"]
            assert (
                sum(
                    sample[key]
                    for key in (
                        "waiting_execution",
                        "executing",
                        "awaiting_review",
                        "reviewing",
                    )
                )
                == sample["unfinished"]
            )
            assert sample["executing"] <= slots
            assert sample["reviewing"] <= 1


def test_metrics_include_the_entire_cohort_and_separate_correction_needs() -> None:
    report = simulate(scenario())
    fifo, priority = report["policies"]
    assert fifo["metrics"]["turnaround"] == {
        "cohort_size": 4,
        "observed": 4,
        "pending": 0,
        "mean": 8.0,
        "p50": 7,
        "p95": 11,
        "max": 11,
    }
    assert priority["metrics"]["turnaround_by_group"]["corrected"]["mean"] == 7
    assert priority["metrics"]["turnaround_by_group"]["first_pass"]["mean"] == 25 / 3
    assert [t["turnaround_delta"] for t in report["comparison"]["tasks"]] == [-4, 0, 2, 2]
    assert [t["first_review_wait_delta"] for t in report["comparison"]["tasks"]] == [0, 0, 2, 2]
    assert simulate(scenario(correction_task_ids=[]))["policies"][0]["metrics"][
        "turnaround_by_group"
    ]["corrected"] == {
        "cohort_size": 0,
        "observed": 0,
        "pending": 0,
        "mean": None,
        "p50": None,
        "p95": None,
        "max": None,
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_version": "review-capacity-v1"},
        {"unknown": 2},
        {"task_count": 0},
        {"task_count": 101},
        {"task_count": True},
        {"arrival_interval": -1},
        {"arrival_interval": 10001},
        {"arrival_interval": 4000},
        {"execution_slots": 0},
        {"execution_slots": 9},
        {"execution_ticks": 0},
        {"execution_ticks": 101},
        {"execution_ticks": 1.0},
        {"review_ticks": 0},
        {"correction_ticks": 0},
        {"observation_horizon": -1},
        {"observation_horizon": 10001},
        {"drain_deadline": 50001},
        {"drain_deadline": 2},
        {"correction_task_ids": None},
        {"correction_task_ids": [True]},
        {"correction_task_ids": [0.0]},
        {"correction_task_ids": [4]},
        {"correction_task_ids": [-1]},
        {"correction_task_ids": [0, 0]},
        {"correction_task_ids": [2, 1]},
        {"correction_task_ids": ["0"]},
    ],
)
def test_invalid_scenarios_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        simulate(scenario(**overrides))


@pytest.mark.parametrize("inputs", [None, [], {}, {"task_count": 4}])
def test_incomplete_or_non_object_scenarios_are_rejected(inputs: Any) -> None:
    with pytest.raises(ValueError):
        simulate(inputs)


def test_fixed_scenario_is_deterministic_and_detached_from_caller() -> None:
    inputs = json.loads(Path("experiments/review-rework/scenario.json").read_text())
    report = simulate(inputs)
    assert report == simulate(inputs)
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert report["scenario_sha256"] == hashlib.sha256(canonical.encode()).hexdigest()
    inputs["correction_task_ids"].clear()
    assert report["inputs"]["correction_task_ids"] == [3, 7, 11, 15, 19, 23]


def test_fixed_workload_mean_improves_while_most_tasks_finish_later() -> None:
    inputs = json.loads(Path("experiments/review-rework/scenario.json").read_text())
    report = simulate(inputs)
    fifo, priority = report["policies"]
    for policy in (fifo, priority):
        assert policy["drain"]["complete"] is True
        assert policy["metrics"]["execution_busy_ticks"] == 24 * 8 + 6 * 4
        assert policy["metrics"]["review_busy_ticks"] == 30 * 6
        assert policy["metrics"]["review_rounds_completed"] == 30
    assert priority["metrics"]["turnaround"]["mean"] < fifo["metrics"]["turnaround"]["mean"]
    assert (
        priority["metrics"]["first_review_wait"]["mean"]
        > fifo["metrics"]["first_review_wait"]["mean"]
    )
    assert priority["drain"]["tick"] > fifo["drain"]["tick"]
    assert sum(t["turnaround_delta"] > 0 for t in report["comparison"]["tasks"]) > 12
    # The last correction occupies execution while the only reviewer has nothing ready.
    last = priority["tasks"][-1]["attempts"][-1]
    assert (last["execution_start_tick"], last["ready_tick"]) == (182, 186)
    at_182 = next(s for s in priority["samples"] if s["tick"] == 182)
    assert at_182["reviewing"] == at_182["awaiting_review"] == 0


def test_maximum_services_and_all_corrected_tasks_remain_bounded(tmp_path: Path) -> None:
    inputs = scenario(
        task_count=100,
        arrival_interval=100,
        execution_slots=1,
        execution_ticks=100,
        review_ticks=100,
        correction_ticks=100,
        correction_task_ids=list(range(100)),
        observation_horizon=10000,
        drain_deadline=50000,
    )
    manifest = export_attempt(tmp_path, inputs, "upper-bound", experiment_type="review-rework")
    report = json.loads((tmp_path / "upper-bound/report.json").read_text())
    assert manifest["scenario_sha256"] == report["scenario_sha256"]
    for policy in report["policies"]:
        assert policy["drain"]["complete"] is True
        assert policy["metrics"]["review_rounds_completed"] == 200
        assert policy["metrics"]["execution_busy_ticks"] == 20000
        assert policy["metrics"]["review_busy_ticks"] == 20000
        assert policy["metrics"]["turnaround_by_group"]["first_pass"]["mean"] is None


@pytest.mark.parametrize("experiment_type", ["review-capacity", "review-rework"])
def test_cli_uses_the_selected_experiments_default_scenario(
    experiment_type: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = Path("experiments") / experiment_type / "scenario.json"
    destination = tmp_path / source
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "sys.argv", ["cli", "experiment", experiment_type, "--attempt-id", "default"]
    )
    cli.main()
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["experiment_type"] == experiment_type
    saved = tmp_path / ".lab/experiments" / experiment_type / "default/scenario.json"
    assert json.loads(saved.read_text()) == json.loads(source.read_text())


def test_cli_exports_both_orders_without_initializing_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(json.dumps(scenario()))
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    argv = ["cli", "experiment", "review-rework", "--scenario", str(scenario_file), "--attempt-id"]
    manifests = []
    for attempt_id in ("first", "repeat"):
        monkeypatch.setattr("sys.argv", [*argv, attempt_id])
        cli.main()
        manifest = json.loads(capsys.readouterr().out)
        manifests.append(manifest)
        directory = tmp_path / ".lab/experiments/review-rework" / attempt_id
        assert json.loads((directory / "manifest.json").read_text()) == manifest
        for file in ("scenario", "report"):
            assert (
                hashlib.sha256((directory / f"{file}.json").read_bytes()).hexdigest()
                == manifest[f"{file}_sha256"]
            )
        report = json.loads((directory / "report.json").read_text())
        assert report == simulate(scenario())
        assert manifest["model_version"] == "review-rework-v1"
        assert manifest["provenance"] == "synthetic_event_time_model"
        assert manifest["experiment_type"] == "review-rework"
        assert manifest["status"] == "complete"
        with pytest.raises(ValueError, match="experiment_type"):
            read_attempt(directory.parent, attempt_id)
    assert manifests[0]["report_sha256"] == manifests[1]["report_sha256"]
    assert sorted(path.name for path in (tmp_path / ".lab").iterdir()) == ["experiments"]
    saved = {p: p.read_bytes() for p in (tmp_path / ".lab").rglob("*.json")}
    with pytest.raises(FileExistsError):
        cli.main()
    assert all(path.read_bytes() == data for path, data in saved.items())


def test_new_experiment_preserves_export_path_and_type_bounds(tmp_path: Path) -> None:
    for attempt_id in ("../escape", "/absolute", "a/b", ".."):
        with pytest.raises(ValueError, match="ID"):
            export_attempt(tmp_path, scenario(), attempt_id, experiment_type="review-rework")
    with pytest.raises(ValueError, match="experiment type"):
        export_attempt(tmp_path, scenario(), "unknown", experiment_type="unknown")
    assert list(tmp_path.iterdir()) == []


def test_cli_rejects_gateway_for_rework(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LAB_ROOT", str(tmp_path))
    monkeypatch.setattr(
        "sys.argv",
        [
            "cli",
            "--gateway",
            "http://127.0.0.1:8765",
            "experiment",
            "review-rework",
        ],
    )
    with pytest.raises(SystemExit, match="locally only"):
        cli.main()
    assert list(tmp_path.iterdir()) == []
