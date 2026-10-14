"""Read-only projections of canonical activity for the operator dashboard."""

import math
from typing import Any

from sqlalchemy import func, select

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
        started_at = None
        completed_at = None
        if latest:
            latest_actor = latest["actor"]
            status = latest["action"].removeprefix("worker.")

            # Find started/completed timestamps for the latest instance
            latest_lifecycle = [item for item in lifecycle if item["actor"] == latest_actor]
            started_events = [
                item for item in latest_lifecycle if item["action"] == "worker.started"
            ]
            completed_events = [
                item for item in latest_lifecycle if item["action"] == "worker.completed"
            ]

            if started_events:
                ts = started_events[-1]["timestamp"]
                if math.isfinite(ts) and ts >= 0:
                    started_at = ts
            if completed_events:
                ts = completed_events[-1]["timestamp"]
                if math.isfinite(ts) and ts >= 0 and ts <= now:
                    completed_at = ts

            if status == "started":
                status = "running"
                if run["status"] == "revoked":
                    status = "revoked"
                elif now - latest["timestamp"] > 120:
                    status = "unknown"
            stage = role

        allowed_actions = sorted(CAPABILITIES[role])
        duration_seconds = None
        if started_at is not None and completed_at is not None:
            if 0 <= started_at <= completed_at <= now and math.isfinite(completed_at - started_at):
                duration_seconds = completed_at - started_at

        agents.append(
            {
                "role": role,
                "status": status,
                "instance_id": latest["actor"] if latest else None,
                "last_activity": matching[-1]["timestamp"] if matching else None,
                "allowed_actions": allowed_actions,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_seconds": duration_seconds,
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
    now = store.clock()
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

        # Flow object aggregates with nested counts dict
        status_counts = list(
            connection.execute(
                select(
                    store.runs.c.status, func.count(store.runs.c.run_id).label("count")
                ).group_by(store.runs.c.status)
            ).mappings()
        )
        status_map = {row["status"]: row["count"] for row in status_counts}

        counts = {
            "running": status_map.get("running", 0),
            "awaiting_review": status_map.get("awaiting_review", 0),
            "accepted": status_map.get("accepted", 0),
            "rejected": status_map.get("rejected", 0),
            "revoked": status_map.get("revoked", 0),
        }

        # Oldest running workflow age
        oldest_running_ts = connection.execute(
            select(func.min(store.runs.c.created_at)).where(store.runs.c.status == "running")
        ).scalar_one()

        oldest_workflow_age_seconds = None if counts["running"] > 0 else 0
        if (
            oldest_running_ts is not None
            and oldest_running_ts <= now
            and math.isfinite(oldest_running_ts)
        ):
            oldest_workflow_age_seconds = now - oldest_running_ts

        # Oldest review age
        journal_table = store.journal.events
        oldest_review_ts = connection.execute(
            select(func.min(journal_table.c.timestamp)).where(
                (
                    journal_table.c.run_id.in_(
                        select(store.runs.c.run_id).where(store.runs.c.status == "awaiting_review")
                    )
                )
                & (journal_table.c.action == "run.ready")
            )
        ).scalar_one()

        oldest_review_age_seconds = None if counts["awaiting_review"] > 0 else 0
        if (
            counts["awaiting_review"] > 0
            and oldest_review_ts is not None
            and oldest_review_ts <= now
            and math.isfinite(oldest_review_ts)
        ):
            oldest_review_age_seconds = now - oldest_review_ts

        # Telemetry: oldest pending age (same transaction)
        outbox = store.journal.outbox
        pending_count = connection.execute(
            select(func.count(outbox.c.sequence)).where(outbox.c.delivered == 0)
        ).scalar_one()

        oldest_pending_age_seconds = None if pending_count > 0 else 0
        last_error = ""
        if pending_count > 0:
            oldest_pending_ts = connection.execute(
                select(func.min(journal_table.c.timestamp)).where(
                    journal_table.c.sequence.in_(
                        select(outbox.c.sequence).where(outbox.c.delivered == 0)
                    )
                )
            ).scalar_one()

            if (
                oldest_pending_ts is not None
                and oldest_pending_ts <= now
                and math.isfinite(oldest_pending_ts)
            ):
                oldest_pending_age_seconds = now - oldest_pending_ts

            latest_error = connection.execute(
                select(outbox.c.last_error)
                .where((outbox.c.delivered == 0) & (outbox.c.last_error != ""))
                .order_by(outbox.c.sequence.desc())
                .limit(1)
            ).scalar()
            if latest_error:
                last_error = latest_error

    summaries = [
        summarize(dict(run), [dict(row) for row in rows if row["run_id"] == run["run_id"]], now)
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
        "flow": {
            "observed_at": now,
            "scope": "all_runs",
            "counts": counts,
            "oldest_workflow_age_seconds": oldest_workflow_age_seconds,
            "oldest_review_age_seconds": oldest_review_age_seconds,
        },
        "telemetry": {
            "enabled": telemetry_enabled,
            "pending": pending_count,
            "oldest_pending_age_seconds": oldest_pending_age_seconds,
            "last_error": last_error,
        },
    }
