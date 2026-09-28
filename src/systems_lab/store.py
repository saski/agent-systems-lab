"""Operational authority, independent of agent prompts and workflow checkpoints."""

import hashlib
import json
import secrets
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    select,
)

from systems_lab.journal import Journal, JournalConflict

CAPABILITIES = {
    "researcher": frozenset({"model.call", "system.describe"}),
    "builder": frozenset({"model.call", "simulation.run"}),
    "reviewer": frozenset({"model.call", "simulation.review"}),
}
POLICY_DIGEST = hashlib.sha256(
    json.dumps({role: sorted(actions) for role, actions in CAPABILITIES.items()}).encode()
).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class ControlError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class Store:
    def __init__(self, url: str, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30}
            if url.startswith("sqlite")
            else {},
        )
        if url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def sqlite_connect(dbapi_connection: Any, _record: Any) -> None:
                dbapi_connection.isolation_level = None
                dbapi_connection.execute("PRAGMA recursive_triggers=ON")

            @event.listens_for(self.engine, "begin")
            def sqlite_begin(connection: Any) -> None:
                connection.exec_driver_sql("BEGIN IMMEDIATE")

        metadata = MetaData()
        self.runs = Table(
            "runs",
            metadata,
            Column("run_id", String, primary_key=True),
            Column("status", String, nullable=False),
            Column("scenario", JSON, nullable=False),
            Column("artifacts", JSON, nullable=False),
            Column("created_at", Float, nullable=False),
            Column("policy_digest", String, nullable=False),
            Column("owner", String, nullable=False),
            Column("model_mode", String, nullable=False),
        )
        self.grants = Table(
            "grants",
            metadata,
            Column("token_hash", String, primary_key=True),
            Column("run_id", String, nullable=False),
            Column("role", String, nullable=False),
            Column("instance_id", String, nullable=False),
            Column("expires_at", Float, nullable=False),
            Column("max_calls", Integer, nullable=False),
            Column("used_calls", Integer, nullable=False),
        )
        self.events = Table(
            "events",
            metadata,
            Column("id", String, primary_key=True),
            Column("run_id", String, nullable=False),
            Column("timestamp", Float, nullable=False),
            Column("actor", String, nullable=False),
            Column("action", String, nullable=False),
            Column("decision", String, nullable=False),
            Column("detail", String, nullable=False),
            Column("model_mode", String, nullable=False),
        )
        metadata.create_all(self.engine)
        self.journal = Journal(self.engine, clock)
        self.journal.import_legacy(self.events)

    def close(self) -> None:
        self.engine.dispose()

    def _event(
        self,
        connection: Any,
        run_id: str,
        actor: str,
        action: str,
        decision: str,
        detail: str = "",
        *,
        key: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.journal.append(
                connection, run_id, actor, action, decision, detail, key=key, data=data
            )
        except JournalConflict as error:
            raise ControlError(409, str(error)) from error

    def create_run(self, scenario: dict[str, Any]) -> str:
        run_id = str(uuid.uuid4())
        with self.engine.begin() as connection:
            connection.execute(
                self.runs.insert().values(
                    run_id=run_id,
                    status="running",
                    scenario=scenario,
                    artifacts={},
                    created_at=self.clock(),
                    policy_digest=POLICY_DIGEST,
                    owner="saski",
                    model_mode="fixture",
                )
            )
            self._event(
                connection, run_id, "operator", "run.create", "allow", key=f"run:{run_id}:create"
            )
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = (
                connection.execute(select(self.runs).where(self.runs.c.run_id == run_id))
                .mappings()
                .first()
            )
            if row is None:
                raise ControlError(404, "Unknown run")
            result = dict(row)
            result["digest"] = digest(
                {
                    "scenario": result["scenario"],
                    "artifacts": result["artifacts"],
                    "policy_digest": result["policy_digest"],
                }
            )
            result["events"] = [
                dict(event)
                for event in connection.execute(
                    select(self.journal.events)
                    .where(self.journal.events.c.run_id == run_id)
                    .order_by(self.journal.events.c.sequence)
                ).mappings()
            ]
            result["instances"] = [
                dict(grant)
                for grant in connection.execute(
                    select(
                        self.grants.c.instance_id,
                        self.grants.c.role,
                        self.grants.c.expires_at,
                        self.grants.c.used_calls,
                        self.grants.c.max_calls,
                    ).where(self.grants.c.run_id == run_id)
                ).mappings()
            ]
            return result

    def issue_grant(
        self, run_id: str, role: str, ttl_seconds: int, max_calls: int
    ) -> dict[str, str]:
        if role not in CAPABILITIES:
            raise ControlError(422, "Unknown role")
        token = secrets.token_urlsafe(32)
        instance_id = f"{role}-{uuid.uuid4()}"
        with self.engine.begin() as connection:
            status = connection.execute(
                select(self.runs.c.status).where(self.runs.c.run_id == run_id).with_for_update()
            ).scalar_one_or_none()
            if status != "running":
                raise ControlError(403, "Run is not active")
            connection.execute(
                self.grants.insert().values(
                    token_hash=digest(token),
                    run_id=run_id,
                    role=role,
                    instance_id=instance_id,
                    expires_at=self.clock() + ttl_seconds,
                    max_calls=max_calls,
                    used_calls=0,
                )
            )
            self._event(connection, run_id, "operator", "grant.issue", "allow", instance_id)
        return {"token": token, "instance_id": instance_id}

    def authorize(self, token: str, action: str) -> dict[str, Any]:
        reason = ""
        grant: dict[str, Any] = {}
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.grants)
                    .where(self.grants.c.token_hash == digest(token))
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ControlError(401, "Invalid task credential")
            grant = dict(row)
            status = connection.execute(
                select(self.runs.c.status).where(self.runs.c.run_id == grant["run_id"])
            ).scalar_one()
            if status != "running":
                reason = "Run is not active"
            elif grant["expires_at"] <= self.clock():
                reason = "Task credential expired"
            elif action not in CAPABILITIES[grant["role"]]:
                reason = "Operation is outside this role"
            elif grant["used_calls"] >= grant["max_calls"]:
                reason = "Operation budget exhausted"
            else:
                updated = connection.execute(
                    self.grants.update()
                    .where(
                        self.grants.c.token_hash == digest(token),
                        self.grants.c.used_calls < self.grants.c.max_calls,
                    )
                    .values(used_calls=self.grants.c.used_calls + 1)
                )
                if updated.rowcount != 1:
                    reason = "Operation budget exhausted"
            self._event(
                connection,
                grant["run_id"],
                grant["instance_id"],
                action,
                "deny" if reason else "allow",
                reason,
            )
        if reason:
            raise ControlError(403, reason)
        return grant

    def artifact(self, run_id: str, name: str, content: Any) -> Any:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.runs).where(self.runs.c.run_id == run_id).with_for_update()
                )
                .mappings()
                .one()
            )
            if row["status"] != "running":
                raise ControlError(403, "Run is not active")
            artifacts = dict(row["artifacts"])
            if name in artifacts:
                return artifacts[name]
            artifacts[name] = content
            updated = connection.execute(
                self.runs.update()
                .where(self.runs.c.run_id == run_id, self.runs.c.status == "running")
                .values(artifacts=artifacts)
            )
            if updated.rowcount != 1:
                raise ControlError(403, "Run is no longer active")
            self._event(
                connection,
                run_id,
                "gateway",
                "artifact.record",
                "allow",
                name,
                key=f"artifact:{run_id}:{name}",
                data={"digest": digest(content)},
            )
        return content

    def revoke(self, run_id: str) -> None:
        self.get_run(run_id)
        with self.engine.begin() as connection:
            connection.execute(
                self.runs.update().where(self.runs.c.run_id == run_id).values(status="revoked")
            )
            self._event(
                connection, run_id, "operator", "run.revoke", "allow", key=f"run:{run_id}:revoke"
            )

    def ready(self, run_id: str) -> None:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.runs).where(self.runs.c.run_id == run_id).with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ControlError(404, "Unknown run")
            if row["status"] == "awaiting_review":
                return
            if row["status"] != "running":
                raise ControlError(403, "Run is not active")
            if not row["artifacts"].get("review", {}).get("valid"):
                raise ControlError(409, "Passing review required")
            updated = connection.execute(
                self.runs.update()
                .where(self.runs.c.run_id == run_id, self.runs.c.status == "running")
                .values(status="awaiting_review")
            )
            if updated.rowcount != 1:
                raise ControlError(403, "Run is no longer active")
            self._event(connection, run_id, "orchestrator", "run.ready", "allow")

    def decide(self, run_id: str, expected_digest: str, approve: bool) -> str:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(self.runs).where(self.runs.c.run_id == run_id).with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ControlError(404, "Unknown run")
            if row["status"] not in {"running", "awaiting_review"}:
                raise ControlError(403, "Run is not active")
            current = digest(
                {
                    "scenario": row["scenario"],
                    "artifacts": row["artifacts"],
                    "policy_digest": row["policy_digest"],
                }
            )
            if current != expected_digest:
                raise ControlError(409, "Artifacts changed; inspect the current digest")
            review = row["artifacts"].get("review", {})
            if approve and not review.get("valid"):
                raise ControlError(409, "A passing deterministic review is required")
            status = "accepted" if approve else "rejected"
            updated = connection.execute(
                self.runs.update()
                .where(self.runs.c.run_id == run_id, self.runs.c.status == row["status"])
                .values(status=status)
            )
            if updated.rowcount != 1:
                raise ControlError(403, "Run status changed during the decision")
            self._event(
                connection,
                run_id,
                "operator",
                "run.decision",
                "allow",
                f"{status}:{expected_digest}",
            )
        return status

    def worker_event(self, run_id: str, instance_id: str, outcome: str, executor: str) -> None:
        with self.engine.begin() as connection:
            registered = connection.execute(
                select(self.grants.c.role).where(
                    self.grants.c.run_id == run_id,
                    self.grants.c.instance_id == instance_id,
                )
            ).scalar_one_or_none()
            if registered is None:
                raise ControlError(404, "Unknown worker instance")
            self._event(
                connection,
                run_id,
                instance_id,
                f"worker.{outcome}",
                "record",
                f"role={registered}; executor={executor}",
                key=f"worker:{instance_id}:{outcome}",
            )

    @contextmanager
    def operation(self, identity: dict[str, Any], action: str) -> Iterator[None]:
        started = time.perf_counter()
        decision = "allow"
        try:
            yield
        except Exception:
            decision = "error"
            raise
        finally:
            with self.engine.begin() as connection:
                self._event(
                    connection,
                    identity["run_id"],
                    identity["instance_id"],
                    f"{action}.completed",
                    decision,
                    data={"duration_ms": max(0, (time.perf_counter() - started) * 1000)},
                )
