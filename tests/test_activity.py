from pathlib import Path

from fastapi.testclient import TestClient

from systems_lab.gateway import create_app
from systems_lab.store import Store
from tests.test_gateway import ADMIN, SCENARIO, grant, new_run

VIEWER = {"Authorization": "Bearer readonly-test-token"}


def test_viewer_can_follow_stages_but_cannot_change_a_run(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'dashboard.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        assert client.get("/api/activity").status_code == 401
        run_id = new_run(client)
        credential = client.post(
            f"/runs/{run_id}/grants", headers=ADMIN, json={"role": "researcher"}
        ).json()
        started = {
            "instance_id": credential["instance_id"],
            "executor": "process",
            "outcome": "started",
        }
        client.post(f"/runs/{run_id}/workers", headers=ADMIN, json=started).raise_for_status()
        response = client.get("/api/activity", headers=VIEWER)
        assert response.status_code == 200
        snapshot = response.json()
        assert snapshot["integrity"]["valid"]
        assert snapshot["runs"][0]["stage"] == "researcher"
        assert snapshot["runs"][0]["agents"][0]["status"] == "running"
        assert (
            client.get(f"/api/activity?after={snapshot['cursor']}", headers=VIEWER).json()["events"]
            == []
        )
        assert client.post(f"/runs/{run_id}/revoke", headers=VIEWER).status_code == 401
        assert client.post("/runs", headers=VIEWER, json={"scenario": SCENARIO}).status_code == 401
        assert (
            client.get(
                "/api/activity", headers={"Authorization": f"Bearer {credential['token']}"}
            ).status_code
            == 401
        )
        client.post(
            f"/runs/{run_id}/workers", headers=ADMIN, json={**started, "outcome": "completed"}
        )
        builder = grant(client, run_id, "builder")
        client.post("/tools/simulation.run", headers=builder).raise_for_status()
        reviewer = grant(client, run_id, "reviewer")
        client.post("/tools/simulation.review", headers=reviewer).raise_for_status()
        client.post(f"/runs/{run_id}/ready", headers=ADMIN).raise_for_status()
        current = client.get(f"/api/activity/{run_id}", headers=VIEWER).json()
        assert current["run"]["stage"] == "human_review"
        assert all(event["trace_id"] == current["run"]["trace_id"] for event in current["events"])
        assert "readonly-test-token" not in response.text
        assert "operator-test-token" not in response.text
        assert response.headers["cache-control"] == "no-store"
    store.close()


def test_unconfirmed_old_worker_is_not_shown_as_live(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'old.db'}", clock=lambda: now[0])
    run_id = store.create_run(SCENARIO)
    credential = store.issue_grant(run_id, "builder", 120, 12)
    store.worker_event(run_id, credential["instance_id"], "started", "process")
    now[0] += 121
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        run = client.get("/api/activity", headers=VIEWER).json()["runs"][0]
        assert run["agents"][1]["status"] == "unknown"
        store.revoke(run_id)
        run = client.get("/api/activity", headers=VIEWER).json()["runs"][0]
        assert run["stage"] == "revoked"
        assert run["agents"][1]["status"] == "revoked"
    store.close()
