"""Deterministic outer workflow with durable, digest-bound human review."""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, TypedDict

import httpx
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from systems_lab.runtime import AgentResult

IMAGE = "agent-systems-lab:local"
NETWORK = "agent-systems-lab-workers"


class WorkflowState(TypedDict, total=False):
    run_id: str
    research: dict[str, Any]
    build: dict[str, Any]
    review: dict[str, Any]
    digest: str
    status: str


class ControlClient:
    def __init__(self, url: str, token: str) -> None:
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.request(method, self.url + path, headers=self.headers, json=body)
            response.raise_for_status()
            return response.json()


class WorkerExecutor:
    def __init__(
        self, root: Path, control: ControlClient, kind: Literal["process", "docker"] = "process"
    ) -> None:
        self.root = root
        self.control = control
        self.kind = kind

    def run(self, run_id: str, role: str) -> AgentResult:
        credential = self.control.request("POST", f"/runs/{run_id}/grants", {"role": role})

        def event(outcome: str) -> None:
            self.control.request(
                "POST",
                f"/runs/{run_id}/workers",
                {
                    "instance_id": credential["instance_id"],
                    "outcome": outcome,
                    "executor": self.kind,
                },
            )

        gateway_url = "http://gateway:8000" if self.kind == "docker" else self.control.url
        payload = json.dumps(
            {"role": role, "gateway_url": gateway_url, "token": credential["token"]}
        )
        if self.kind == "docker":
            command = [
                "docker",
                "run",
                "--rm",
                "-i",
                "--name",
                f"asl-{run_id}-{role}",
                "--label",
                f"systems-lab.run={run_id}",
                "--network",
                NETWORK,
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges:true",
                "--pids-limit=64",
                "--memory=384m",
                "--cpus=1",
                "--user=10001:10001",
                "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
                IMAGE,
                "python",
                "-m",
                "systems_lab.worker",
            ]
        else:
            command = [sys.executable, "-m", "systems_lab.worker"]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self.root / ".lab" / "worker-home"),
            "LAB_ROOT": str(self.root),
            "PYTHONUNBUFFERED": "1",
            "LANGSMITH_TRACING": "false",
        }
        if self.kind == "docker":
            # Host Docker credentials configure the CLI; none are passed into the container.
            for variable in ("HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"):
                if variable in os.environ:
                    environment[variable] = os.environ[variable]
        event("started")
        try:
            result = subprocess.run(
                command,
                input=payload,
                text=True,
                capture_output=True,
                cwd=self.root,
                env=environment,
                timeout=90,
                check=True,
            )
        except subprocess.TimeoutExpired:
            self.control.request("POST", f"/runs/{run_id}/revoke")
            if self.kind == "docker":
                stop_containers(run_id)
            event("timed_out")
            raise RuntimeError("Worker timed out; run revoked") from None
        except subprocess.CalledProcessError:
            self.control.request("POST", f"/runs/{run_id}/revoke")
            event("failed")
            raise RuntimeError(f"{role} worker failed; run revoked") from None
        try:
            parsed = AgentResult.model_validate_json(result.stdout)
        except ValueError:
            self.control.request("POST", f"/runs/{run_id}/revoke")
            event("failed")
            raise RuntimeError(f"{role} returned invalid evidence; run revoked") from None
        event("completed")
        return parsed


def stop_containers(run_id: str) -> list[str]:
    result = subprocess.run(
        ["docker", "ps", "-q", "--filter", f"label=systems-lab.run={run_id}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    containers = result.stdout.split()
    if containers:
        subprocess.run(["docker", "kill", *containers], check=True, capture_output=True, timeout=15)
    return containers


@contextmanager
def workflow(checkpoint: Path, control: ControlClient, executor: WorkerExecutor) -> Iterator[Any]:
    graph = StateGraph(WorkflowState)

    def specialist(role: str, key: str) -> Any:
        def execute(state: WorkflowState) -> dict[str, Any]:
            return {key: executor.run(state["run_id"], role).model_dump()}

        return execute

    def validate(state: WorkflowState) -> dict[str, Any]:
        snapshot = control.request("GET", f"/runs/{state['run_id']}")
        if not snapshot["artifacts"].get("review", {}).get("valid"):
            raise ValueError("Deterministic review failed")
        control.request("POST", f"/runs/{state['run_id']}/ready")
        return {"digest": snapshot["digest"]}

    def human_review(state: WorkflowState) -> dict[str, Any]:
        interrupt(
            {
                "run_id": state["run_id"],
                "digest": state["digest"],
                "action": "Inspect artifacts, then approve or reject with this exact digest.",
            }
        )
        snapshot = control.request("GET", f"/runs/{state['run_id']}")
        if snapshot["status"] not in {"accepted", "rejected"}:
            raise ValueError("An operator decision is required before resuming")
        if snapshot["digest"] != state["digest"]:
            raise ValueError("The approved artifact digest does not match this checkpoint")
        return {"status": snapshot["status"]}

    graph.add_node("researcher", specialist("researcher", "research"))
    graph.add_node("builder", specialist("builder", "build"))
    graph.add_node("reviewer", specialist("reviewer", "review"))
    graph.add_node("validate", validate)
    graph.add_node("human_review", human_review)
    for left, right in [
        (START, "researcher"),
        ("researcher", "builder"),
        ("builder", "reviewer"),
        ("reviewer", "validate"),
        ("validate", "human_review"),
        ("human_review", END),
    ]:
        graph.add_edge(left, right)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        yield graph.compile(checkpointer=saver)
