"""Run explicitly against a disposable Compose stack, including in CI."""

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from systems_lab.orchestrator import IMAGE, NETWORK, ControlClient
from tests.test_gateway import SCENARIO

pytestmark = pytest.mark.skipif(
    os.environ.get("LAB_CONTAINER_TESTS") != "1", reason="Requires the explicit Compose test stack"
)
ROOT = Path(__file__).resolve().parents[1]
URL = "http://127.0.0.1:8765"


def command(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        list(args),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr[-5000:]
    return result.stdout


def control() -> ControlClient:
    return ControlClient(URL, (ROOT / ".lab" / "operator.token").read_text().strip())


def test_container_workflow_reaches_review_and_can_be_accepted() -> None:
    output = command(
        sys.executable, "-m", "systems_lab.cli", "--gateway", URL, "run", "--executor", "docker"
    )
    run = json.loads(output)
    assert run["status"] == "awaiting_review"
    snapshot = control().request("GET", f"/runs/{run['run_id']}")
    assert snapshot["artifacts"]["review"]["valid"]
    assert len(snapshot["instances"]) == 3
    accepted = command(
        sys.executable,
        "-m",
        "systems_lab.cli",
        "--gateway",
        URL,
        "decide",
        run["run_id"],
        "--digest",
        run["digest"],
        "--approve",
    )
    assert json.loads(accepted)["status"] == "accepted"


def test_worker_network_cannot_reach_external_network_or_database() -> None:
    network = json.loads(command("docker", "network", "inspect", NETWORK))[0]
    assert network["Internal"] is True
    probe = (
        "import socket\n"
        "for host, port in [('1.1.1.1', 443), ('db', 5432)]:\n"
        " try:\n"
        "  socket.create_connection((host, port), timeout=2).close()\n"
        " except OSError:\n"
        "  continue\n"
        " raise SystemExit('unexpected network access')\n"
        "print('network boundaries verified')\n"
    )
    output = command(
        "docker",
        "run",
        "--rm",
        "--network",
        NETWORK,
        "--cap-drop=ALL",
        "--read-only",
        IMAGE,
        "python",
        "-c",
        probe,
    )
    assert "network boundaries verified" in output


def test_revocation_blocks_calls_and_kills_only_labelled_run_containers() -> None:
    client = control()
    run_id = client.request("POST", "/runs", {"scenario": SCENARIO})["run_id"]
    grant = client.request("POST", f"/runs/{run_id}/grants", {"role": "researcher"})
    container = command(
        "docker",
        "run",
        "-d",
        "--rm",
        "--network",
        NETWORK,
        "--label",
        f"systems-lab.run={run_id}",
        IMAGE,
        "python",
        "-c",
        "import time; time.sleep(120)",
    ).strip()
    unrelated = command(
        "docker",
        "run",
        "-d",
        "--rm",
        "--network",
        NETWORK,
        "--label",
        "systems-lab.run=unrelated-test-run",
        IMAGE,
        "python",
        "-c",
        "import time; time.sleep(120)",
    ).strip()
    try:
        output = command(
            sys.executable,
            "-m",
            "systems_lab.cli",
            "--gateway",
            URL,
            "revoke",
            run_id,
            "--stop-containers",
        )
        assert json.loads(output)["status"] == "revoked"
        running = command("docker", "ps", "-q", "--no-trunc")
        assert container not in running
        assert unrelated in running
        response = httpx.post(
            f"{URL}/tools/system.describe",
            headers={"Authorization": f"Bearer {grant['token']}"},
            timeout=10,
        )
        assert response.status_code == 403
    finally:
        subprocess.run(["docker", "stop", container, unrelated], capture_output=True, timeout=15)


def test_postgres_history_rejects_mutation_and_survives_concurrent_writes() -> None:
    from concurrent.futures import ThreadPoolExecutor

    client = control()
    with ThreadPoolExecutor(max_workers=4) as executor:
        run_ids = list(
            executor.map(
                lambda _: client.request("POST", "/runs", {"scenario": SCENARIO})["run_id"],
                range(8),
            )
        )
    assert len(set(run_ids)) == 8
    before = client.request("GET", "/history/checkpoint")
    assert before["valid"]
    for mutation in [
        "UPDATE journal SET decision='changed'",
        "DELETE FROM journal",
        "TRUNCATE journal",
    ]:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "lab",
                "-d",
                "lab",
                "-c",
                mutation,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=ROOT,
        )
        assert result.returncode != 0
        assert "append-only history" in result.stderr
    assert client.request("GET", "/history/checkpoint") == before


@pytest.mark.skipif(os.environ.get("LAB_OTEL_TESTS") != "1", reason="Requires optional Collector")
def test_real_collector_receives_journal_spans_and_readonly_dashboard(tmp_path: Path) -> None:
    import time

    client = control()
    run_id = client.request("POST", "/runs", {"scenario": SCENARIO})["run_id"]
    viewer = (ROOT / ".lab" / "viewer.token").read_text().strip()
    headers = {"Authorization": f"Bearer {viewer}"}
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        response = httpx.get(f"{URL}/api/activity", headers=headers, timeout=10)
        response.raise_for_status()
        snapshot = response.json()
        if snapshot["telemetry"]["enabled"] and snapshot["telemetry"]["pending"] == 0:
            break
        time.sleep(0.5)
    else:
        raise AssertionError("Collector did not acknowledge pending spans")
    assert snapshot["integrity"]["valid"]
    assert httpx.get(f"{URL}/dashboard", timeout=10).status_code == 200
    assert httpx.post(f"{URL}/runs/{run_id}/revoke", headers=headers, timeout=10).status_code == 401
    destination = tmp_path / "traces.jsonl"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        copied = subprocess.run(
            [
                "docker",
                "compose",
                "cp",
                "otel-collector:/var/lib/otelcol/traces.jsonl",
                str(destination),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=ROOT,
        )
        if copied.returncode == 0 and run_id in destination.read_text():
            break
        time.sleep(0.5)
    else:
        raise AssertionError("Collector accepted spans but its file has no matching run")
