import json
import socket
import uuid
from pathlib import Path

import httpx
import pytest
from langgraph.types import Command

from systems_lab.admission import RUNTIME_ROOT, AdmissionCoordinator, batch_lock
from systems_lab.cli import execute, initialize, local_control, parser
from systems_lab.orchestrator import ControlClient, WorkerExecutor, workflow
from systems_lab.store import ControlError, Store
from tests.test_gateway import SCENARIO


def test_ambiguous_launch_retains_wip_until_explicit_terminal_reconciliation(
    tmp_path: Path,
) -> None:
    token = initialize(tmp_path)
    store = Store(f"sqlite:///{tmp_path / '.lab/control.db'}")
    try:
        batch = store.admission.create(str(uuid.uuid4()), SCENARIO)
        identity, item = batch["batch_id"], batch["items"][0]["item_id"]
        epoch = store.admission.claim(identity, "crashed-owner", 0)
        run_id = store.admission.reserve(identity, "crashed-owner", epoch, item)
        store.admission.transition(identity, "crashed-owner", epoch, item, "launching")
        with local_control(tmp_path, token) as control:
            path = f"/batches/{identity}"
            blocked = control.request("POST", path + "/advance")
            assert blocked["wip"] == 1
            assert blocked["items"][0]["state"] == "blocked"
            assert blocked["items"][1]["run_id"] is None
            with pytest.raises(httpx.HTTPStatusError):
                control.request("POST", path + "/reconcile")
            control.request("POST", f"/runs/{run_id}/revoke")
            assert control.request("POST", path + "/advance")["wip"] == 1
            reconciled = control.request("POST", path + "/reconcile")
            assert reconciled["wip"] == 0
            assert reconciled["items"][0]["outcome"] == "revoked"
            assert reconciled["items"][1]["run_id"] is None
            next_run = control.request("POST", path + "/advance")
            assert next_run["items"][1]["state"] == "awaiting_review"
            assert store.get_run(run_id)["instances"] == []
    finally:
        store.close()


def test_real_worker_failure_revokes_and_blocks_without_automatic_retry(tmp_path: Path) -> None:
    token = initialize(tmp_path)
    store = Store(f"sqlite:///{tmp_path / '.lab/control.db'}")
    missing_agent_root = tmp_path / "missing-agents"
    missing_agent_root.mkdir()
    try:
        batch = store.admission.create(str(uuid.uuid4()), SCENARIO)
        with local_control(tmp_path, token) as control:
            coordinator = AdmissionCoordinator(
                tmp_path, store, control, runtime_root=missing_agent_root
            )
            with pytest.raises(ControlError, match="Workflow blocked"):
                coordinator.advance(batch["batch_id"])
            blocked = store.admission.snapshot(batch["batch_id"])
            run = store.get_run(blocked["items"][0]["run_id"])
            assert run["status"] == "revoked"
            assert any(event["action"] == "worker.failed" for event in run["events"])
            assert blocked["wip"] == 1 and blocked["items"][1]["run_id"] is None
            assert coordinator.advance(batch["batch_id"])["wip"] == 1
            assert len(store.get_run(run["run_id"])["instances"]) == 1
            assert coordinator.advance(batch["batch_id"], reconcile=True)["wip"] == 0
            exports = list(
                (tmp_path / ".lab/experiments/fixture-workflow-admission" / batch["batch_id"]).glob(
                    "*.json"
                )
            )
            assert exports
            evidence = json.loads(exports[-1].read_text())
            assert evidence["provenance"] == "fixture_workflow"
            assert evidence["evidence_kind"] == "derived_snapshot"
            assert token not in exports[-1].read_text()
            assert not (tmp_path / ".lab/experiments/review-capacity").exists()
    finally:
        store.close()


def test_gateway_outage_preserves_admission_and_never_launches_next_work(tmp_path: Path) -> None:
    token = initialize(tmp_path)
    store = Store(f"sqlite:///{tmp_path / '.lab/control.db'}")
    try:
        batch = store.admission.create(str(uuid.uuid4()), SCENARIO)
        epoch = store.admission.claim(batch["batch_id"], "owner", 0)
        store.admission.reserve(batch["batch_id"], "owner", epoch, batch["items"][0]["item_id"])
        before = store.admission.snapshot(batch["batch_id"])
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            # Keep the port reserved while no gateway is listening.
            control = ControlClient(f"http://127.0.0.1:{listener.getsockname()[1]}", token)
            with pytest.raises(httpx.TransportError):
                AdmissionCoordinator(tmp_path, store, control).advance(batch["batch_id"])
        after = store.admission.snapshot(batch["batch_id"])
        assert after["items"] == before["items"]
        assert after["wip"] == 1
    finally:
        store.close()


def test_checkpoint_resume_and_decision_cannot_bypass_batch_owner_or_authority(
    tmp_path: Path,
) -> None:
    token = initialize(tmp_path)
    with local_control(tmp_path, token) as control:
        batch = control.request("POST", "/batches", {})
        path = f"/batches/{batch['batch_id']}"
        admitted = control.request("POST", path + "/advance")
        run_id = admitted["items"][0]["run_id"]
        run = control.request("GET", f"/runs/{run_id}")
        with batch_lock(tmp_path, batch["batch_id"]):
            with pytest.raises(ControlError, match="still active"):
                execute(
                    parser().parse_args(["decide", run_id, "--digest", run["digest"], "--approve"]),
                    tmp_path,
                    control,
                )
        with workflow(
            tmp_path / ".lab/checkpoints.db", control, WorkerExecutor(RUNTIME_ROOT, control)
        ) as graph:
            with pytest.raises(ValueError, match="operator decision"):
                graph.invoke(Command(resume=True), {"configurable": {"thread_id": run_id}})
        assert control.request("POST", path + "/advance")["items"] == admitted["items"]
        control.request("POST", f"/runs/{run_id}/revoke")
        after = control.request("POST", path + "/advance")
        assert after["items"][0]["outcome"] == "revoked"
        assert after["items"][1]["state"] == "awaiting_review"
