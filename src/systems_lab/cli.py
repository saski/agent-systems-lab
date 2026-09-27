"""Operator interface. The fixture demo makes no external model calls."""

import argparse
import json
import os
import secrets
import shlex
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import uvicorn
from langgraph.types import Command

from systems_lab.gateway import create_app
from systems_lab.orchestrator import ControlClient, WorkerExecutor, stop_containers, workflow
from systems_lab.store import Store


def initialize(root: Path) -> str:
    state = root / ".lab"
    state.mkdir(mode=0o700, exist_ok=True)
    secret_file = state / "operator.token"
    if not secret_file.exists():
        descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(32))
    token = secret_file.read_text().strip()
    env_file = state / "gateway.env"
    if not env_file.exists():
        descriptor = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(f"LAB_OPERATOR_TOKEN={token}\n")
    return token


@contextmanager
def local_control(root: Path, token: str) -> Iterator[ControlClient]:
    store = Store(f"sqlite:///{root / '.lab' / 'control.db'}")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(store, token),
            log_level="error",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    try:
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("Local control gateway failed to start")
            time.sleep(0.02)
        yield ControlClient(f"http://127.0.0.1:{port}", token)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        store.close()


def export_run(root: Path, snapshot: dict[str, Any]) -> Path:
    directory = root / ".lab" / "runs" / snapshot["run_id"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "run.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n")
    for name, artifact in snapshot["artifacts"].items():
        (directory / f"{name}.json").write_text(
            json.dumps(artifact, indent=2, allow_nan=False) + "\n"
        )
    return directory


def execute(args: argparse.Namespace, root: Path, control: ControlClient) -> None:
    if args.command in {"run", "demo"}:
        scenario = json.loads((root / args.scenario).read_text())
        run_id = control.request("POST", "/runs", {"scenario": scenario})["run_id"]
        executor = WorkerExecutor(root, control, args.executor)
        with workflow(root / ".lab" / "checkpoints.db", control, executor) as graph:
            graph.invoke({"run_id": run_id}, {"configurable": {"thread_id": run_id}})
        snapshot = control.request("GET", f"/runs/{run_id}")
        artifacts = export_run(root, snapshot)
        next_command = ["uv", "run", "systems-lab"]
        if args.gateway:
            next_command.extend(["--gateway", args.gateway])
        next_command.extend(["decide", run_id, "--digest", snapshot["digest"], "--approve"])
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": snapshot["status"],
                    "model_mode": "fixture",
                    "executor": args.executor,
                    "digest": snapshot["digest"],
                    "artifacts": str(artifacts),
                    "next": shlex.join(next_command),
                },
                indent=2,
            )
        )
    elif args.command == "status":
        snapshot = control.request("GET", f"/runs/{args.run_id}")
        export_run(root, snapshot)
        print(json.dumps(snapshot, indent=2))
    elif args.command == "decide":
        checkpoint = root / ".lab" / "checkpoints.db"
        config = {"configurable": {"thread_id": args.run_id}}
        with workflow(checkpoint, control, WorkerExecutor(root, control)) as graph:
            state = graph.get_state(config)
            if not state.values or state.values.get("digest") != args.digest:
                raise ValueError("No pending local checkpoint matches this run and digest")
            snapshot = control.request("GET", f"/runs/{args.run_id}")
            desired = "accepted" if args.approve else "rejected"
            if snapshot["status"] in {"running", "awaiting_review"}:
                control.request(
                    "POST",
                    f"/runs/{args.run_id}/decision",
                    {
                        "digest": args.digest,
                        "approve": args.approve,
                    },
                )
            elif snapshot["status"] != desired or snapshot["digest"] != args.digest:
                raise ValueError("Run does not match the requested decision")
            result = graph.invoke(Command(resume=True), config)
        export_run(root, control.request("GET", f"/runs/{args.run_id}"))
        print(json.dumps({"run_id": args.run_id, "status": result["status"]}))
    elif args.command == "revoke":
        control.request("POST", f"/runs/{args.run_id}/revoke")
        stopped = stop_containers(args.run_id) if args.stop_containers else []
        print(json.dumps({"run_id": args.run_id, "status": "revoked", "stopped": stopped}))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Governed multi-agent systems playground")
    result.add_argument("--gateway", help="External gateway; omitted uses a local SQLite gateway")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Generate local operator credentials without printing them")
    commands.add_parser("gateway", help="Serve the trusted control gateway")
    for name in ("run", "demo"):
        command = commands.add_parser(name, help="Run the fixture experiment and pause for review")
        command.add_argument("--scenario", default="experiments/backlog-feedback/scenario.json")
        command.add_argument("--executor", choices=["process", "docker"], default="process")
    status = commands.add_parser("status", help="Inspect a run and its audit events")
    status.add_argument("run_id")
    decision = commands.add_parser("decide", help="Approve or reject the exact reviewed evidence")
    decision.add_argument("run_id")
    decision.add_argument("--digest", required=True)
    choice = decision.add_mutually_exclusive_group(required=True)
    choice.add_argument("--approve", action="store_true")
    choice.add_argument("--reject", action="store_true")
    revoke = commands.add_parser(
        "revoke", help="Revoke access, optionally kill run-labelled containers"
    )
    revoke.add_argument("run_id")
    revoke.add_argument("--stop-containers", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    root = Path(os.environ.get("LAB_ROOT", ".")).resolve()
    if args.command == "gateway":
        token = os.environ["LAB_OPERATOR_TOKEN"]
        database = os.environ["LAB_DATABASE_URL"]
        store = Store(database)
        try:
            uvicorn.run(create_app(store, token), host="0.0.0.0", port=8000, access_log=False)
        finally:
            store.close()
        return
    token = initialize(root)
    if args.command == "init":
        print("Local credentials ready in .lab/ (ignored by Git).")
        return
    if args.command in {"run", "demo"} and args.executor == "docker" and not args.gateway:
        raise SystemExit("Docker workers require --gateway http://127.0.0.1:8765")
    if args.gateway:
        execute(args, root, ControlClient(args.gateway, token))
    else:
        with local_control(root, token) as control:
            execute(args, root, control)


if __name__ == "__main__":
    main()
