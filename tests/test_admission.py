from pathlib import Path

import httpx
import pytest

from systems_lab.cli import execute, initialize, local_control, parser


def test_two_fixture_tasks_keep_one_place_through_review_and_restart(tmp_path: Path) -> None:
    token = initialize(tmp_path)
    with local_control(tmp_path, token) as control:
        batch = control.request("POST", "/batches", {})
        path = f"/batches/{batch['batch_id']}"
        first = control.request("POST", path + "/advance")
        assert first["wip"] == 1
        assert first["items"][0]["state"] == "awaiting_review"
        assert first["items"][1]["state"] == "queued"
        assert first["items"][1]["run_id"] is None
        run_id = first["items"][0]["run_id"]
        run = control.request("GET", f"/runs/{run_id}")
        assert len(run["instances"]) == 3
        assert all(instance["used_calls"] == 3 for instance in run["instances"])
        assert control.request("POST", path + "/advance")["items"] == first["items"]

    with local_control(tmp_path, token) as control:
        restarted = control.request("POST", path + "/advance")
        assert restarted["items"] == first["items"]
        after = control.request("GET", f"/runs/{run_id}")
        assert after["digest"] == run["digest"]
        assert after["instances"] == run["instances"]


@pytest.mark.parametrize("approve", [True, False])
def test_manual_decisions_admit_the_next_task_once(tmp_path: Path, approve: bool) -> None:
    token = initialize(tmp_path)
    with local_control(tmp_path, token) as control:
        batch = control.request("POST", "/batches", {})
        path = f"/batches/{batch['batch_id']}"
        first = control.request("POST", path + "/advance")
        run_id = first["items"][0]["run_id"]
        snapshot = control.request("GET", f"/runs/{run_id}")
        with pytest.raises(httpx.HTTPStatusError) as denied:
            control.request(
                "POST", f"/runs/{run_id}/decision", {"digest": "stale", "approve": approve}
            )
        assert denied.value.response.status_code == 409
        assert control.request("POST", path + "/advance")["items"] == first["items"]
        decision = parser().parse_args(
            [
                "decide",
                run_id,
                "--digest",
                snapshot["digest"],
                "--approve" if approve else "--reject",
            ]
        )
        execute(decision, tmp_path, control)
        second = control.request("POST", path + "/advance")
        assert second["wip"] == 1
        assert second["items"][0]["state"] == "released"
        assert second["items"][0]["outcome"] == ("accepted" if approve else "rejected")
        assert second["items"][1]["state"] == "awaiting_review"
        second_id = second["items"][1]["run_id"]
        assert second_id != run_id
        assert control.request("GET", f"/runs/{run_id}")["instances"] == snapshot["instances"]
        assert control.request("POST", path + "/advance")["items"] == second["items"]
        final_run = control.request("GET", f"/runs/{second_id}")
        execute(
            parser().parse_args(["decide", second_id, "--digest", final_run["digest"], "--reject"]),
            tmp_path,
            control,
        )
        complete = control.request("POST", path + "/advance")
        assert complete["complete"] and complete["wip"] == 0
        assert len([e for e in complete["events"] if e["state"] == "reserved"]) == 2
        assert control.request("POST", path + "/advance")["items"] == complete["items"]


def test_batch_cli_exposes_create_status_advance_and_reconcile(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    token = initialize(tmp_path)
    with local_control(tmp_path, token) as control:
        execute(parser().parse_args(["batch", "create"]), tmp_path, control)
        batch = json.loads(capsys.readouterr().out)
        assert len(batch["items"]) == 2 and batch["wip"] == 0
        for action in ("status", "advance", "reconcile"):
            args = parser().parse_args(["batch", action, batch["batch_id"]])
            assert args.batch_action == action
        execute(parser().parse_args(["batch", "status", batch["batch_id"]]), tmp_path, control)
        assert json.loads(capsys.readouterr().out) == batch
