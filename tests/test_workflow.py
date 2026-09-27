from pathlib import Path

import pytest
from langgraph.types import Command

from systems_lab.cli import initialize, local_control
from systems_lab.orchestrator import WorkerExecutor, workflow
from tests.test_gateway import SCENARIO

ROOT = Path(__file__).resolve().parents[1]


def test_three_specialists_pause_and_resume_after_restart_without_repeating_work(tmp_path) -> None:
    token = initialize(tmp_path)
    with local_control(tmp_path, token) as control:
        run_id = control.request("POST", "/runs", {"scenario": SCENARIO})["run_id"]
        executor = WorkerExecutor(ROOT, control)
        checkpoint = tmp_path / "workflow.db"
        config = {"configurable": {"thread_id": run_id}}
        with workflow(checkpoint, control, executor) as graph:
            pending = graph.invoke({"run_id": run_id}, config)
            assert pending["__interrupt__"]
            assert pending["review"]["model_mode"] == "fixture"
        snapshot = control.request("GET", f"/runs/{run_id}")
        assert {instance["role"] for instance in snapshot["instances"]} == {
            "researcher",
            "builder",
            "reviewer",
        }
        assert all(instance["used_calls"] == 3 for instance in snapshot["instances"])
        assert snapshot["artifacts"]["review"]["valid"]
        assert snapshot["status"] == "awaiting_review"
        completed = [event for event in snapshot["events"] if event["action"] == "worker.completed"]
        assert len(completed) == 3
        control.request(
            "POST",
            f"/runs/{run_id}/decision",
            {
                "digest": snapshot["digest"],
                "approve": True,
            },
        )
        with workflow(checkpoint, control, executor) as graph:
            finished = graph.invoke(Command(resume=True), config)
        assert finished["status"] == "accepted"
        after = control.request("GET", f"/runs/{run_id}")
        assert len(after["instances"]) == 3
        assert after["digest"] == snapshot["digest"]


def test_resuming_a_checkpoint_cannot_bypass_operator_authorization(tmp_path) -> None:
    token = initialize(tmp_path)
    with local_control(tmp_path, token) as control:
        run_id = control.request("POST", "/runs", {"scenario": SCENARIO})["run_id"]
        checkpoint = tmp_path / "workflow.db"
        config = {"configurable": {"thread_id": run_id}}
        with workflow(checkpoint, control, WorkerExecutor(ROOT, control)) as graph:
            graph.invoke({"run_id": run_id}, config)
            with pytest.raises(ValueError, match="operator decision"):
                graph.invoke(Command(resume=True), config)
