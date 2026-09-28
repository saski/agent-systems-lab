"""A closed set of authorized operations; no arbitrary shell, paths, or URLs."""

import hmac
import json
import math
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from systems_lab.activity import activity, summarize
from systems_lab.simulation import Scenario, simulate
from systems_lab.store import ControlError, Store
from systems_lab.telemetry import TelemetryDelivery

TOOLS = {
    "researcher": ("describe_system", "system.describe"),
    "builder": ("run_simulation", "simulation.run"),
    "reviewer": ("review_simulation", "simulation.review"),
}


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: dict[str, Any]


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["researcher", "builder", "reviewer"]
    ttl_seconds: int = Field(default=120, ge=1, le=300)
    max_calls: int = Field(default=12, ge=1, le=40)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str
    approve: bool


class WorkerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instance_id: str
    outcome: Literal["started", "completed", "failed", "timed_out"]
    executor: Literal["process", "docker"]


def review_simulation(result: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for row in result["observations"]:
        conserved = math.isclose(
            row["backlog_start"] + row["arrivals"] - row["completed"],
            row["backlog_end"],
            abs_tol=1e-8,
        )
        checks.append(
            conserved
            and row["backlog_end"] >= 0
            and 0 <= row["completed"] <= row["available_backlog"]
            and row["completed"] <= row["capacity"]
        )
    return {
        "valid": bool(checks) and all(checks),
        "checked_steps": len(checks),
        "checks": ["stock conservation", "nonnegative backlog", "bounded service"],
        "limitation": "Numerical invariants do not establish that this model describes reality.",
    }


def fixture_completion(body: dict[str, Any], role: str) -> dict[str, Any]:
    messages = body.get("messages", [])
    last = messages[-1] if messages else {}
    if last.get("role") == "tool":
        message = {
            "role": "assistant",
            "content": json.dumps(
                {
                    "role": role,
                    "model_mode": "fixture",
                    "summary": f"Scripted {role} completed its authorized tool call.",
                    "evidence": json.loads(last["content"]),
                }
            ),
        }
        reason = "stop"
    else:
        name, _ = TOOLS[role]
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": f"fixture_{role}",
                    "type": "function",
                    "function": {"name": name, "arguments": "{}"},
                }
            ],
        }
        reason = "tool_calls"
    return {
        "id": f"fixture-{role}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "fixture",
        "choices": [{"index": 0, "message": message, "finish_reason": reason}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def create_app(
    store: Store,
    operator_token: str,
    viewer_token: str | None = None,
    delivery: TelemetryDelivery | None = None,
) -> FastAPI:
    if not operator_token:
        raise ValueError("An operator credential is required")
    delivery = delivery or TelemetryDelivery.from_environment(store.journal)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> Any:
        delivery.start()
        try:
            yield
        finally:
            delivery.stop()

    app = FastAPI(title="Agent Systems Lab control gateway", lifespan=lifespan)
    static = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static, check_dir=False), name="static")

    @app.middleware("http")
    async def protect_browser(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path == "/dashboard" or request.url.path.startswith("/static/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'self'"
            )
        return response

    @app.get("/dashboard", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(static / "index.html")

    @app.exception_handler(ControlError)
    async def control_error(_request: Any, error: ControlError) -> JSONResponse:
        return JSONResponse({"detail": error.detail}, status_code=error.status)

    def credential(authorization: Annotated[str, Header()] = "") -> str:
        if not authorization.startswith("Bearer "):
            raise ControlError(401, "Bearer credential required")
        return authorization.removeprefix("Bearer ")

    def operator(token: str = Depends(credential)) -> None:
        if not hmac.compare_digest(token, operator_token):
            raise ControlError(401, "Operator credential required")

    def viewer(token: str = Depends(credential)) -> None:
        if not hmac.compare_digest(token, operator_token) and not (
            viewer_token and hmac.compare_digest(token, viewer_token)
        ):
            raise ControlError(401, "Viewer credential required")

    @app.get("/api/activity", dependencies=[Depends(viewer)])
    def get_activity(after: int = Query(default=0, ge=0)) -> dict[str, Any]:
        return activity(store, after, delivery.enabled)

    @app.get("/api/activity/{run_id}", dependencies=[Depends(viewer)])
    def run_activity(run_id: str) -> dict[str, Any]:
        run = store.get_run(run_id)
        return {
            "run": summarize(run, run["events"], store.clock()),
            "events": run["events"],
            "integrity": store.journal.verify(),
        }

    @app.get("/history/checkpoint", dependencies=[Depends(viewer)])
    def checkpoint() -> dict[str, Any]:
        return store.journal.verify()

    @app.post("/history/verify", dependencies=[Depends(viewer)])
    def verify(checkpoint: dict[str, Any]) -> dict[str, Any]:
        return store.journal.verify(checkpoint)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "model_mode": "fixture"}

    @app.post("/runs", dependencies=[Depends(operator)])
    def create_run(request: RunRequest) -> dict[str, str]:
        try:
            scenario = Scenario.from_dict(request.scenario)
            if scenario.steps > 1000:
                raise ValueError("Gateway allows at most 1000 simulation steps")
            simulate(scenario)
        except (ValueError, TypeError) as error:
            raise ControlError(422, str(error)) from error
        return {"run_id": store.create_run(request.scenario)}

    @app.get("/runs/{run_id}", dependencies=[Depends(operator)])
    def get_run(run_id: str) -> dict[str, Any]:
        return store.get_run(run_id)

    @app.post("/runs/{run_id}/grants", dependencies=[Depends(operator)])
    def grant(run_id: str, request: GrantRequest) -> dict[str, str]:
        return store.issue_grant(run_id, request.role, request.ttl_seconds, request.max_calls)

    @app.post("/runs/{run_id}/workers", dependencies=[Depends(operator)])
    def worker_event(run_id: str, event: WorkerEvent) -> dict[str, str]:
        store.worker_event(run_id, event.instance_id, event.outcome, event.executor)
        return {"status": "recorded"}

    @app.post("/runs/{run_id}/revoke", dependencies=[Depends(operator)])
    def revoke(run_id: str) -> dict[str, str]:
        store.revoke(run_id)
        return {"status": "revoked"}

    @app.post("/runs/{run_id}/ready", dependencies=[Depends(operator)])
    def ready(run_id: str) -> dict[str, str]:
        store.ready(run_id)
        return {"status": "awaiting_review"}

    @app.post("/runs/{run_id}/decision", dependencies=[Depends(operator)])
    def decide(run_id: str, request: Decision) -> dict[str, str]:
        return {"status": store.decide(run_id, request.digest, request.approve)}

    @app.post("/tools/{action}")
    def call_tool(action: str, token: str = Depends(credential)) -> dict[str, Any]:
        identity = store.authorize(token, action)
        with store.operation(identity, action):
            run_id = identity["run_id"]
            run = store.get_run(run_id)
            if action == "system.describe":
                result = {
                    "stock": "unfinished tasks",
                    "inflow": "arrivals per time step",
                    "outflow": "completed tasks per time step",
                    "feedback": "capacity responds to observed backlog relative to a target",
                    "boundary": "single queue, homogeneous tasks, no retries or worker learning",
                    "hypothesis": "Observation delay can alter controller stability; compare runs.",
                    "provenance": "Original teaching example; not a reproduction of Meadows' book.",
                }
                return store.artifact(run_id, "research", result)
            if action == "simulation.run":
                result = simulate(Scenario.from_dict(run["scenario"]))
                return store.artifact(run_id, "simulation", result)
            if action == "simulation.review":
                if "simulation" not in run["artifacts"]:
                    raise ControlError(409, "Simulation evidence is required before review")
                return store.artifact(
                    run_id, "review", review_simulation(run["artifacts"]["simulation"])
                )
            raise ControlError(403, "Unknown operation")

    @app.post("/v1/chat/completions")
    def model_call(body: dict[str, Any], token: str = Depends(credential)) -> dict[str, Any]:
        if body.get("model") != "fixture" or body.get("stream"):
            store.authorize(token, "model.route.unregistered")
        identity = store.authorize(token, "model.call")
        with store.operation(identity, "model.call"):
            return fixture_completion(body, identity["role"])

    return app
