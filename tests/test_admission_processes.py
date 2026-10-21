import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from systems_lab.admission import batch_lock
from systems_lab.cli import initialize
from systems_lab.orchestrator import ControlClient
from systems_lab.store import ControlError, Store
from tests.test_gateway import SCENARIO


def wait_until(predicate: Callable[[], bool], timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Timed out waiting for the process boundary")
        time.sleep(0.02)


def stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


GATED_GATEWAY = """
import asyncio, sys, time
from pathlib import Path
import uvicorn
from systems_lab.gateway import create_app
from systems_lab.store import Store
root, port = Path(sys.argv[1]), int(sys.argv[2])
store = Store(f"sqlite:///{root / '.lab/control.db'}")
app = create_app(store, (root / '.lab/operator.token').read_text().strip(),
                 admission_root=root, admission_gateway_url=f"http://127.0.0.1:{port}")
@app.middleware('http')
async def gate(request, call_next):
    if request.url.path == '/v1/chat/completions':
        (root / 'worker-entered').touch()
        deadline = time.monotonic() + 20
        while not (root / 'release-worker').exists() and time.monotonic() < deadline:
            await asyncio.sleep(.02)
    return await call_next(request)
uvicorn.run(app, host='127.0.0.1', port=port, log_level='error', access_log=False)
"""


def test_competing_coordinator_process_cannot_launch_while_first_graph_is_active(
    tmp_path: Path,
) -> None:
    token = initialize(tmp_path)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {
        **os.environ,
        "LAB_ROOT": str(tmp_path),
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "",
    }
    server = subprocess.Popen(
        [sys.executable, "-c", GATED_GATEWAY, str(tmp_path), str(port)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    control = ControlClient(f"http://127.0.0.1:{port}", token)

    def healthy() -> bool:
        assert server.poll() is None, server.communicate(timeout=1)
        try:
            return control.request("GET", "/health", timeout=0.2)["status"] == "ok"
        except httpx.TransportError:
            return False

    try:
        wait_until(healthy)
        batch = control.request("POST", "/batches", {})
        with ThreadPoolExecutor(max_workers=1) as pool:
            active = pool.submit(control.request, "POST", f"/batches/{batch['batch_id']}/advance")
            try:
                wait_until(lambda: (tmp_path / "worker-entered").exists())
                competitor = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "systems_lab.cli",
                        "batch",
                        "advance",
                        batch["batch_id"],
                    ],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert competitor.returncode != 0
                assert "409" in competitor.stderr
                during = control.request("GET", f"/batches/{batch['batch_id']}")
                assert during["wip"] == 1 and during["items"][1]["run_id"] is None
            finally:
                (tmp_path / "release-worker").touch()
            finished = active.result(timeout=20)
        assert finished["items"][0]["state"] == "awaiting_review"
        run = control.request("GET", f"/runs/{finished['items'][0]['run_id']}")
        assert len(run["instances"]) == 3
    finally:
        (tmp_path / "release-worker").touch()
        stop(server)


INHERITED_OWNER = """
import subprocess, sys, time
from pathlib import Path
from systems_lab.admission import batch_lock
root, identity = Path(sys.argv[1]), sys.argv[2]
with batch_lock(root, identity) as descriptor:
    child = subprocess.Popen([sys.executable, '-c',
        'import sys; sys.stdin.buffer.read(1)'], pass_fds=(descriptor,),
        stdin=(root / 'worker.fifo').open('rb'), stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    (root / 'child.pid').write_text(str(child.pid))
    while True:
        time.sleep(.1)
"""


def test_worker_inherits_lock_after_owner_death_and_ambiguous_run_stays_reserved(
    tmp_path: Path,
) -> None:
    initialize(tmp_path)
    store = Store(f"sqlite:///{tmp_path / '.lab/control.db'}")
    batch = store.admission.create(str(uuid.uuid4()), SCENARIO)
    epoch = store.admission.claim(batch["batch_id"], "crashed", 0)
    run_id = store.admission.reserve(
        batch["batch_id"], "crashed", epoch, batch["items"][0]["item_id"]
    )
    store.admission.transition(
        batch["batch_id"], "crashed", epoch, batch["items"][0]["item_id"], "launching"
    )
    fifo = tmp_path / "worker.fifo"
    os.mkfifo(fifo)
    # RDWR keeps opening deterministic; the worker blocks on data, not on a timer.
    writer = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
    owner = subprocess.Popen(
        [sys.executable, "-c", INHERITED_OWNER, str(tmp_path), batch["batch_id"]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_until(lambda: (tmp_path / "child.pid").exists())
        owner.kill()
        owner.wait(timeout=5)
        with pytest.raises(ControlError, match="still active"):
            with batch_lock(tmp_path, batch["batch_id"]):
                pytest.fail("A live inherited worker must exclude takeover")
        assert store.admission.snapshot(batch["batch_id"])["wip"] == 1
        os.write(writer, b"x")

        def worker_exited() -> bool:
            try:
                with batch_lock(tmp_path, batch["batch_id"]):
                    return True
            except ControlError:
                return False

        wait_until(worker_exited)
        from systems_lab.cli import local_control

        token = (tmp_path / ".lab/operator.token").read_text().strip()
        with local_control(tmp_path, token) as control:
            result = control.request("POST", f"/batches/{batch['batch_id']}/advance")
            assert result["items"][0]["state"] == "blocked"
            assert result["items"][1]["run_id"] is None
        assert store.get_run(run_id)["instances"] == []
    finally:
        os.write(writer, b"x")
        os.close(writer)
        stop(owner)
        store.close()
