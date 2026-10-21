"""Operator-driven, local fixture admission with inherited process exclusion."""

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from systems_lab.orchestrator import ControlClient, WorkerExecutor, workflow
from systems_lab.store import ControlError, Store

RUNTIME_ROOT = Path(__file__).resolve().parents[2]


def fixture_scenario() -> dict[str, Any]:
    return json.loads((RUNTIME_ROOT / "experiments/backlog-feedback/scenario.json").read_text())


@contextmanager
def batch_lock(root: Path, batch_id: str) -> Iterator[int]:
    if os.name != "posix":
        raise ControlError(409, "Fixture admission requires POSIX process locks")
    import fcntl

    identity = str(uuid.UUID(batch_id))
    directory = root / ".lab" / "admission"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(
        directory / f"{identity}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ControlError(409, "Batch owner or inherited worker is still active") from error
        yield descriptor
    finally:
        # Closing, rather than LOCK_UN, preserves the lock in any surviving child.
        # Lock files are never removed: a second inode would bypass exclusion.
        os.close(descriptor)


class AdmissionCoordinator:
    def __init__(
        self,
        root: Path,
        store: Store,
        control: ControlClient,
        *,
        runtime_root: Path = RUNTIME_ROOT,
    ) -> None:
        database = store.engine.url.database
        if (
            store.engine.dialect.name != "sqlite"
            or database is None
            or (Path(database).resolve() != (root / ".lab" / "control.db").resolve())
        ):
            raise ValueError("Admission lock and SQLite database must share one local LAB_ROOT")
        self.root: Path = root
        self.store: Store = store
        self.control: ControlClient = control
        self.runtime_root: Path = runtime_root

    def advance(self, batch_id: str, *, reconcile: bool = False) -> dict[str, Any]:
        with batch_lock(self.root, batch_id) as descriptor:
            admission = self.store.admission
            batch = admission.snapshot(batch_id)
            owner = str(uuid.uuid4())
            epoch = admission.claim(batch_id, owner, batch["epoch"])
            item = next((item for item in batch["items"] if item["state"] != "released"), None)
            if item is None:
                return self.export(batch_id)
            if item["run_id"] is not None:
                run = self.control.request("GET", f"/runs/{item['run_id']}")
                if item["state"] in {"launching", "blocked"} and not reconcile:
                    admission.transition(
                        batch_id,
                        owner,
                        epoch,
                        item["item_id"],
                        "blocked",
                        reason="Ambiguous launch; revoke or decide, then reconcile",
                    )
                    return self.export(batch_id)
                if run["status"] in {"accepted", "rejected", "revoked"}:
                    admission.transition(
                        batch_id, owner, epoch, item["item_id"], "released", reconciled=reconcile
                    )
                    if reconcile:
                        return self.export(batch_id)
                    batch = admission.snapshot(batch_id)
                    item = next(
                        (item for item in batch["items"] if item["state"] == "queued"), None
                    )
                    if item is None:
                        return self.export(batch_id)
                elif reconcile:
                    raise ControlError(409, "Reconciliation requires a canonical terminal outcome")
                elif item["state"] == "awaiting_review":
                    if run["status"] != "awaiting_review":
                        raise ControlError(409, "Canonical status does not match review wait")
                    return self.export(batch_id)
            elif reconcile:
                raise ControlError(409, "No admitted run to reconcile")

            run_id = admission.reserve(batch_id, owner, epoch, item["item_id"])
            admission.transition(batch_id, owner, epoch, item["item_id"], "launching")
            executor = WorkerExecutor(self.runtime_root, self.control, admission_lock_fd=descriptor)
            try:
                with workflow(
                    self.root / ".lab" / "checkpoints.db", self.control, executor
                ) as graph:
                    graph.invoke({"run_id": run_id}, {"configurable": {"thread_id": run_id}})
                admission.transition(batch_id, owner, epoch, item["item_id"], "awaiting_review")
            except Exception as error:
                admission.transition(
                    batch_id,
                    owner,
                    epoch,
                    item["item_id"],
                    "blocked",
                    reason="Workflow interrupted; explicit reconciliation required",
                )
                self.export(batch_id)
                raise ControlError(
                    409, "Workflow blocked; inspect the run before reconciliation"
                ) from error
            return self.export(batch_id)

    def export(self, batch_id: str) -> dict[str, Any]:
        batch = self.store.admission.snapshot(batch_id)
        runs = {
            item["run_id"]: self.store.get_run(item["run_id"])
            for item in batch["items"]
            if item["run_id"] is not None
        }
        evidence = {
            **batch,
            "observed_at": self.store.clock(),
            "runs": runs,
            "evidence_kind": "derived_snapshot",
            "source": "local_gateway",
        }
        directory = self.root / ".lab" / "experiments" / "fixture-workflow-admission" / batch_id
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{uuid.uuid4().hex}.json").open("x") as stream:
            stream.write(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
        return batch
