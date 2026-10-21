import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from systems_lab.gateway import create_app
from systems_lab.store import Store
from tests.test_gateway import ADMIN, SCENARIO, grant, new_run


def test_gateway_without_local_coordinator_cannot_create_an_unrunnable_batch(
    tmp_path: Path,
) -> None:
    store = Store(f"sqlite:///{tmp_path / 'control.db'}")
    try:
        with TestClient(create_app(store, "operator-test-token")) as client:
            response = client.post("/batches", headers=ADMIN, json={})
            assert response.status_code == 409
    finally:
        store.close()


def test_batch_operations_reject_viewers_workers_and_missing_credentials(tmp_path: Path) -> None:
    (tmp_path / ".lab").mkdir()
    store = Store(f"sqlite:///{tmp_path / '.lab/control.db'}")
    try:
        with TestClient(
            create_app(
                store,
                "operator-test-token",
                "viewer-test-token",
                admission_root=tmp_path,
                admission_gateway_url="http://127.0.0.1:1",
            )
        ) as client:
            batch = client.post("/batches", headers=ADMIN, json={}).json()
            path = f"/batches/{batch['batch_id']}"
            worker = grant(client, new_run(client), "researcher")
            for headers in ({}, {"Authorization": "Bearer viewer-test-token"}, worker):
                assert client.post("/batches", headers=headers, json={}).status_code == 401
                assert client.get(path, headers=headers).status_code == 401
                for operation in ("advance", "reconcile"):
                    assert client.post(f"{path}/{operation}", headers=headers).status_code == 401
            assert client.get(path, headers=ADMIN).json() == batch
    finally:
        store.close()


def test_batch_inputs_are_bounded_and_identity_retries_do_not_duplicate_work(
    tmp_path: Path,
) -> None:
    (tmp_path / ".lab").mkdir()
    store = Store(f"sqlite:///{tmp_path / '.lab/control.db'}")
    try:
        with TestClient(
            create_app(
                store,
                "operator-test-token",
                admission_root=tmp_path,
                admission_gateway_url="http://127.0.0.1:1",
            )
        ) as client:
            identity = str(uuid.uuid4())
            body = {"batch_id": identity}
            first = client.post("/batches", headers=ADMIN, json=body)
            assert first.status_code == 200
            assert client.post("/batches", headers=ADMIN, json=body).json() == first.json()
            for extra in (
                {"wip_limit": 2},
                {"tasks": [1, 2, 3]},
                {"owner": "worker"},
                {"path": "/tmp"},
                {"scenario": SCENARIO},
            ):
                assert (
                    client.post("/batches", headers=ADMIN, json={**body, **extra}).status_code
                    == 422
                )
            assert (
                client.post(
                    "/batches", headers=ADMIN, json={"scenario": {**SCENARIO, "steps": 1001}}
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "/batches", headers=ADMIN, json={**body, "batch_id": "../escape"}
                ).status_code
                == 422
            )
            assert client.get("/batches/not-an-id", headers=ADMIN).status_code == 422
            assert client.get(f"/batches/{uuid.uuid4()}", headers=ADMIN).status_code == 404
    finally:
        store.close()
