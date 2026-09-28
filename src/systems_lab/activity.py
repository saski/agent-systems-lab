"""Read-only projections of canonical activity for the operator dashboard."""

from typing import Any

from sqlalchemy import select

from systems_lab.journal import trace_id
from systems_lab.store import CAPABILITIES, Store


def summarize(run: dict[str, Any], events: list[dict[str, Any]], now: float) -> dict[str, Any]:
    agents = []
    stage = "researcher"
    for role in CAPABILITIES:
        matching = [item for item in events if item["actor"].startswith(f"{role}-")]
        lifecycle = [item for item in matching if item["action"].startswith("worker.")]
        latest = lifecycle[-1] if lifecycle else None
        status = "idle"
        if latest:
            status = latest["action"].removeprefix("worker.")
            if status == "started":
                status = "running"
                if run["status"] == "revoked":
                    status = "revoked"
                elif now - latest["timestamp"] > 120:
                    status = "unknown"
            stage = role
        agents.append(
            {
                "role": role,
                "status": status,
                "instance_id": latest["actor"] if latest else None,
                "last_activity": matching[-1]["timestamp"] if matching else None,
            }
        )
    if agents[-1]["status"] == "completed":
        stage = "validate"
    if run["status"] == "awaiting_review":
        stage = "human_review"
    elif run["status"] in {"accepted", "rejected"}:
        stage = "completed"
    elif run["status"] == "revoked":
        stage = "revoked"
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "created_at": run["created_at"],
        "last_activity": events[-1]["timestamp"] if events else run["created_at"],
        "stage": stage,
        "model_mode": run["model_mode"],
        "trace_id": trace_id(run["run_id"]),
        "agents": agents,
    }


def activity(store: Store, after: int, telemetry_enabled: bool) -> dict[str, Any]:
    integrity = store.journal.verify()
    with store.engine.connect().execution_options(lab_readonly=True) as connection:
        runs = list(
            connection.execute(
                select(store.runs)
                .order_by(store.runs.c.created_at.desc(), store.runs.c.run_id)
                .limit(100)
            ).mappings()
        )
        journal = store.journal.events
        rows = list(
            connection.execute(
                select(journal)
                .where(journal.c.run_id.in_([run["run_id"] for run in runs]))
                .order_by(journal.c.sequence)
            ).mappings()
        )
    summaries = [
        summarize(
            dict(run), [dict(row) for row in rows if row["run_id"] == run["run_id"]], store.clock()
        )
        for run in runs
    ]
    events = store.journal.read(after=after)
    cursor = events[-1]["sequence"] if events else after
    return {
        "cursor": cursor,
        "head": integrity["checked"],
        "has_more": cursor < integrity["checked"],
        "events": events,
        "runs": summaries,
        "integrity": integrity,
        "telemetry": {"enabled": telemetry_enabled, **store.journal.outbox_status()},
    }
