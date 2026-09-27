from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from systems_lab.gateway import create_app
from systems_lab.store import Store

SCENARIO = {
    "steps": 12,
    "initial_backlog": 20,
    "arrivals_per_step": 5,
    "initial_capacity": 5,
    "base_capacity": 5,
    "min_capacity": 0,
    "max_capacity": 15,
    "target_backlog": 10,
    "observation_delay": 2,
    "adjustment_gain": 0.5,
}
ADMIN = {"Authorization": "Bearer operator-test-token"}


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    store = Store(f"sqlite:///{tmp_path / 'control.db'}")
    with TestClient(create_app(store, "operator-test-token")) as value:
        yield value
    store.close()


def new_run(client: TestClient) -> str:
    response = client.post("/runs", headers=ADMIN, json={"scenario": SCENARIO})
    assert response.status_code == 200
    return response.json()["run_id"]


def grant(client: TestClient, run_id: str, role: str, **options) -> dict[str, str]:
    response = client.post(f"/runs/{run_id}/grants", headers=ADMIN, json={"role": role, **options})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_a_researcher_cannot_use_builder_tools_or_issue_its_own_grants(client: TestClient) -> None:
    run_id = new_run(client)
    worker = grant(client, run_id, "researcher")
    assert client.post("/tools/system.describe", headers=worker, json={}).status_code == 200
    denied = client.post("/tools/simulation.run", headers=worker, json={})
    assert denied.status_code == 403
    assert (
        client.post(f"/runs/{run_id}/grants", headers=worker, json={"role": "builder"}).status_code
        == 401
    )
    events = client.get(f"/runs/{run_id}", headers=ADMIN).json()["events"]
    assert all(event["model_mode"] == "fixture" for event in events)
    assert any(
        event["action"] == "simulation.run" and event["decision"] == "deny" for event in events
    )


def test_revocation_blocks_existing_tokens_and_new_tokens(client: TestClient) -> None:
    run_id = new_run(client)
    researcher = grant(client, run_id, "researcher")
    builder = grant(client, run_id, "builder")
    assert client.post(f"/runs/{run_id}/revoke", headers=ADMIN).status_code == 200
    for worker, action in [(researcher, "system.describe"), (builder, "simulation.run")]:
        assert client.post(f"/tools/{action}", headers=worker, json={}).status_code == 403
    assert (
        client.post(f"/runs/{run_id}/grants", headers=ADMIN, json={"role": "reviewer"}).status_code
        == 403
    )


def test_gateway_keeps_runs_separate_and_bounds_operations(client: TestClient) -> None:
    first = new_run(client)
    second = new_run(client)
    builder = grant(client, first, "builder", max_calls=1)
    assert client.post("/tools/simulation.run", headers=builder, json={}).status_code == 200
    assert client.post("/tools/simulation.run", headers=builder, json={}).status_code == 403
    assert client.get(f"/runs/{second}", headers=ADMIN).json()["artifacts"] == {}
    assert client.get(f"/runs/{first}", headers=builder).status_code == 401


def test_approval_is_bound_to_current_artifacts_and_does_not_revive_a_revoked_run(
    client: TestClient,
) -> None:
    run_id = new_run(client)
    builder = grant(client, run_id, "builder")
    client.post("/tools/simulation.run", headers=builder, json={}).raise_for_status()
    reviewer = grant(client, run_id, "reviewer")
    client.post("/tools/simulation.review", headers=reviewer, json={}).raise_for_status()
    snapshot = client.get(f"/runs/{run_id}", headers=ADMIN).json()
    assert (
        client.post(
            f"/runs/{run_id}/decision",
            headers=ADMIN,
            json={"digest": "stale", "approve": True},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/runs/{run_id}/decision",
            headers=ADMIN,
            json={"digest": snapshot["digest"], "approve": True},
        ).status_code
        == 200
    )
    assert client.post("/tools/simulation.run", headers=builder, json={}).status_code == 403
    client.post(f"/runs/{run_id}/revoke", headers=ADMIN).raise_for_status()
    assert (
        client.post(
            f"/runs/{run_id}/decision",
            headers=ADMIN,
            json={"digest": snapshot["digest"], "approve": True},
        ).status_code
        == 403
    )


def test_expired_token_is_rejected_and_raw_token_is_not_stored(tmp_path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'expiry.db'}", clock=lambda: now[0])
    with TestClient(create_app(store, "operator-test-token")) as client:
        run_id = new_run(client)
        headers = grant(client, run_id, "researcher", ttl_seconds=1)
        now[0] += 2
        assert client.post("/tools/system.describe", headers=headers, json={}).status_code == 403
        raw_token = headers["Authorization"].removeprefix("Bearer ").encode()
        assert raw_token not in (tmp_path / "expiry.db").read_bytes()
    store.close()


def test_unknown_roles_tools_and_unregistered_models_fail_closed(client: TestClient) -> None:
    run_id = new_run(client)
    assert (
        client.post(f"/runs/{run_id}/grants", headers=ADMIN, json={"role": "superuser"}).status_code
        == 422
    )
    worker = grant(client, run_id, "researcher")
    assert client.post("/tools/shell.exec", headers=worker, json={}).status_code == 403
    assert (
        client.post(
            "/v1/chat/completions",
            headers=worker,
            json={"model": "unapproved-provider", "messages": []},
        ).status_code
        == 403
    )


def test_gateway_rejects_unbounded_or_nonfinite_computations_before_creating_a_run(
    client: TestClient,
) -> None:
    excessive = {**SCENARIO, "steps": 1001}
    assert client.post("/runs", headers=ADMIN, json={"scenario": excessive}).status_code == 422
    overflowing = {**SCENARIO, "initial_backlog": 1e308, "adjustment_gain": 1e308}
    assert client.post("/runs", headers=ADMIN, json={"scenario": overflowing}).status_code == 422
