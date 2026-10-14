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
        response_text = response.text
        assert "readonly-test-token" not in response_text
        assert "operator-test-token" not in response_text
        assert response.headers["cache-control"] == "no-store"
        store.journal.verify()
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


def test_flow_observed_at_equals_store_clock(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'clock.db'}", clock=lambda: now[0])
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["observed_at"] == 1000.0
        now[0] = 2000.0
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["observed_at"] == 2000.0
    store.close()


def test_flow_scope_all_runs(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'scope.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["scope"] == "all_runs"
    store.close()


def test_flow_counts_zero_when_empty(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'empty.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["counts"]["running"] == 0
        assert response["flow"]["counts"]["awaiting_review"] == 0
        assert response["flow"]["counts"]["accepted"] == 0
        assert response["flow"]["counts"]["rejected"] == 0
        assert response["flow"]["counts"]["revoked"] == 0
    store.close()


def test_flow_counts_beyond_latest_100_view(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'beyond100.db'}", clock=lambda: now[0])
    run_ids = []
    for _ in range(101):
        run_id = store.create_run(SCENARIO)
        run_ids.append(run_id)
        credential = store.issue_grant(run_id, "researcher", 120, 12)
        store.worker_event(run_id, credential["instance_id"], "started", "process")
        now[0] += 1.0

    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["counts"]["running"] == 101
        assert len(response["runs"]) == 100
    store.close()


def test_flow_oldest_workflow_age_seconds(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'age.db'}", clock=lambda: now[0])

    run_id = store.create_run(SCENARIO)
    credential = store.issue_grant(run_id, "researcher", 120, 12)
    store.worker_event(run_id, credential["instance_id"], "started", "process")

    now[0] = 1050.0
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["oldest_workflow_age_seconds"] == 50.0
    store.close()


def test_flow_oldest_workflow_age_zero_when_empty(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'age_empty.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["oldest_workflow_age_seconds"] == 0
    store.close()


def test_flow_oldest_workflow_age_none_when_pending_in_future(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'age_future.db'}", clock=lambda: now[0])

    now[0] = 1000.0
    store.create_run(SCENARIO)

    now[0] = 999.0
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["oldest_workflow_age_seconds"] is None
    store.close()


def test_flow_oldest_review_age_seconds_from_ready_timestamp(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'review_age.db'}", clock=lambda: now[0])

    run_id = store.create_run(SCENARIO)
    credential = store.issue_grant(run_id, "researcher", 120, 12)
    store.worker_event(run_id, credential["instance_id"], "started", "process")

    now[0] = 1050.0
    store.worker_event(run_id, credential["instance_id"], "completed", "process")

    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        builder = grant(client, run_id, "builder")
        client.post("/tools/simulation.run", headers=builder).raise_for_status()
        reviewer = grant(client, run_id, "reviewer")
        client.post("/tools/simulation.review", headers=reviewer).raise_for_status()
        client.post(f"/runs/{run_id}/ready", headers=ADMIN).raise_for_status()

        now[0] = 1100.0
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["oldest_review_age_seconds"] == 50.0
    store.close()


def test_flow_oldest_review_age_zero_when_empty(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'review_age_empty.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["flow"]["oldest_review_age_seconds"] == 0
    store.close()


def test_telemetry_oldest_pending_age_seconds_zero_when_empty(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'pending_empty.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get("/api/activity", headers=VIEWER).json()
        assert response["telemetry"]["oldest_pending_age_seconds"] == 0
    store.close()


def test_telemetry_oldest_pending_age_after_acknowledge(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'pending_ack.db'}", clock=lambda: now[0])

    store.create_run(SCENARIO)

    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        now[0] = 1050.0
        before_ack = client.get("/api/activity", headers=VIEWER).json()
        assert before_ack["telemetry"]["pending"] == 1
        assert before_ack["telemetry"]["oldest_pending_age_seconds"] == 50.0
        initial_events = before_ack["events"]
        initial_sequence = initial_events[0]["sequence"]
        store.journal.verify()

        # Failed acknowledge leaves pending unchanged
        store.journal.acknowledge([initial_sequence], error="temporary failure")
        failed_response = client.get("/api/activity", headers=VIEWER).json()
        assert failed_response["telemetry"]["pending"] == 1
        assert failed_response["telemetry"]["oldest_pending_age_seconds"] == 50.0
        assert failed_response["events"][0]["sequence"] == initial_sequence
        store.journal.verify()

        # Successful acknowledge clears pending
        store.journal.acknowledge([initial_sequence], error=None)
        success_response = client.get("/api/activity", headers=VIEWER).json()
        assert success_response["telemetry"]["pending"] == 0
        assert success_response["telemetry"]["oldest_pending_age_seconds"] == 0
        store.journal.verify()

    store.close()


def test_summarize_run_agents_allowed_actions(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'actions.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        run_id = new_run(client)
        builder = grant(client, run_id, "builder")
        response = client.get(f"/api/activity/{run_id}", headers=VIEWER).json()

        agents = response["run"]["agents"]
        researcher_agent = next(a for a in agents if a["role"] == "researcher")
        assert researcher_agent["allowed_actions"] == ["model.call", "system.describe"]

        builder_agent = next(a for a in agents if a["role"] == "builder")
        assert builder_agent["allowed_actions"] == ["model.call", "simulation.run"]

        reviewer_agent = next(a for a in agents if a["role"] == "reviewer")
        assert reviewer_agent["allowed_actions"] == ["model.call", "simulation.review"]

        # Verify builder endpoint requires builder credentials
        assert client.get(f"/api/activity/{run_id}", headers=builder).status_code == 401
    store.close()


def test_summarize_run_started_at_completed_at_duration(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'lifecycle.db'}", clock=lambda: now[0])

    run_id = store.create_run(SCENARIO)
    credential = store.issue_grant(run_id, "researcher", 120, 12)

    now[0] = 1010.0
    store.worker_event(run_id, credential["instance_id"], "started", "process")

    now[0] = 1035.0
    store.worker_event(run_id, credential["instance_id"], "completed", "process")

    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get(f"/api/activity/{run_id}", headers=VIEWER).json()

        agent = response["run"]["agents"][0]
        assert agent["started_at"] == 1010.0
        assert agent["completed_at"] == 1035.0
        assert agent["duration_seconds"] == 25.0
    store.close()


def test_summarize_run_timing_null_before_completion(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'timing_null.db'}", clock=lambda: now[0])

    run_id = store.create_run(SCENARIO)
    credential = store.issue_grant(run_id, "researcher", 120, 12)
    store.worker_event(run_id, credential["instance_id"], "started", "process")

    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get(f"/api/activity/{run_id}", headers=VIEWER).json()

        agent = response["run"]["agents"][0]
        assert agent["started_at"] == 1000.0
        assert agent["completed_at"] is None
        assert agent["duration_seconds"] is None
    store.close()


def test_activity_permissions_and_tokens_read_only(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'readonly.db'}")
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        run_id = new_run(client)
        response = client.get(f"/api/activity/{run_id}", headers=VIEWER)
        response_text = response.text

        assert "operator-test-token" not in response_text
        assert "readonly-test-token" not in response_text
    store.close()


def test_summarize_run_timing_edge_cases(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'timing_edge.db'}", clock=lambda: now[0])

    # Valid timestamp of 0
    run_id_zero = store.create_run(SCENARIO)
    now[0] = 0.0
    cred_zero = store.issue_grant(run_id_zero, "researcher", 120, 12)
    store.worker_event(run_id_zero, cred_zero["instance_id"], "started", "process")
    now[0] = 10.0
    store.worker_event(run_id_zero, cred_zero["instance_id"], "completed", "process")

    # Future timestamp should yield None age
    now[0] = 2000.0
    run_id_future = store.create_run(SCENARIO)
    cred_future = store.issue_grant(run_id_future, "researcher", 120, 12)
    now[0] = 1000.0
    store.worker_event(run_id_future, cred_future["instance_id"], "started", "process")
    now[0] = 3000.0
    store.worker_event(run_id_future, cred_future["instance_id"], "completed", "process")

    now[0] = 2000.0
    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response_zero = client.get(f"/api/activity/{run_id_zero}", headers=VIEWER).json()
        agent_zero = response_zero["run"]["agents"][0]
        assert agent_zero["started_at"] == 0.0
        assert agent_zero["completed_at"] == 10.0
        assert agent_zero["duration_seconds"] == 10.0

        response_future = client.get(f"/api/activity/{run_id_future}", headers=VIEWER).json()
        agent_future = response_future["run"]["agents"][0]
        assert agent_future["completed_at"] is None
        assert agent_future["duration_seconds"] is None
    store.close()


def test_summarize_run_multiple_instances_latest_only(tmp_path: Path) -> None:
    now = [1000.0]
    store = Store(f"sqlite:///{tmp_path / 'multiple_instances.db'}", clock=lambda: now[0])

    run_id = store.create_run(SCENARIO)

    # First instance: complete lifecycle
    cred1 = store.issue_grant(run_id, "researcher", 120, 12)
    now[0] = 1010.0
    store.worker_event(run_id, cred1["instance_id"], "started", "process")
    now[0] = 1020.0
    store.worker_event(run_id, cred1["instance_id"], "completed", "process")

    # Second instance: completed without started event in lifecycle
    cred2 = store.issue_grant(run_id, "researcher", 120, 12)
    now[0] = 1030.0
    store.worker_event(run_id, cred2["instance_id"], "completed", "process")

    with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
        response = client.get(f"/api/activity/{run_id}", headers=VIEWER).json()
        agent = response["run"]["agents"][0]

        # Latest instance completed without started, should not borrow from previous
        assert agent["instance_id"] == cred2["instance_id"]
        assert agent["status"] == "completed"
        assert agent["started_at"] is None
        assert agent["completed_at"] == 1030.0
        assert agent["duration_seconds"] is None
    store.close()
