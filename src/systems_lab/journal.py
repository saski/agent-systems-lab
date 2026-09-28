"""Canonical append-only history and a separately mutable delivery outbox."""

import hashlib
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import JSON, Column, Float, Integer, MetaData, String, Table, func, select, text
from sqlalchemy.engine import Connection, Engine

GENESIS = "0" * 64


def checksum(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def trace_id(run_id: str) -> str:
    return checksum(f"run:{run_id}")[:32]


def span_id(event_id: str) -> str:
    return checksum(f"event:{event_id}")[:16]


def identity(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"systems-lab:{key}"))


class JournalConflict(ValueError):
    pass


class Journal:
    def __init__(self, engine: Engine, clock: Callable[[], float] = time.time) -> None:
        self.engine = engine
        self.clock = clock
        metadata = MetaData()
        self.events = Table(
            "journal",
            metadata,
            Column("sequence", Integer, primary_key=True, autoincrement=False),
            Column("event_id", String, unique=True, nullable=False),
            Column("event_key", String, unique=True, nullable=False),
            Column("run_id", String, index=True, nullable=False),
            Column("timestamp", Float, nullable=False),
            Column("actor", String, nullable=False),
            Column("action", String, nullable=False),
            Column("decision", String, nullable=False),
            Column("detail", String, nullable=False),
            Column("model_mode", String, nullable=False),
            Column("provenance", String, nullable=False),
            Column("data", JSON, nullable=False),
            Column("trace_id", String, nullable=False),
            Column("span_id", String, nullable=False),
            Column("parent_span_id", String, nullable=False),
            Column("previous_hash", String, nullable=False),
            Column("hash", String, nullable=False),
        )
        self.head = Table(
            "journal_head",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("sequence", Integer, nullable=False),
            Column("hash", String, nullable=False),
        )
        self.outbox = Table(
            "telemetry_outbox",
            metadata,
            Column("sequence", Integer, primary_key=True, autoincrement=False),
            Column("delivered", Integer, nullable=False),
            Column("attempts", Integer, nullable=False),
            Column("last_error", String, nullable=False),
        )
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO journal_head (id, sequence, hash) VALUES (1, 0, :hash) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"hash": GENESIS},
            )
            self._protect(connection, "journal")

    def _protect(self, connection: Connection, table: str, sealed: bool = False) -> None:
        # Table names are internal constants, never user input.
        operations = ["update", "delete"] + (["insert"] if sealed else [])
        if self.engine.dialect.name == "sqlite":
            if not sealed:
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table} "
                        f"WHEN EXISTS (SELECT 1 FROM {table} WHERE sequence=NEW.sequence "
                        "OR event_id=NEW.event_id OR event_key=NEW.event_key) "
                        "BEGIN SELECT RAISE(ABORT, 'append-only history'); END"
                    )
                )
            for operation in operations:
                connection.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation} "
                        f"BEFORE {operation.upper()} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'append-only history'); END"
                    )
                )
        else:
            connection.execute(
                text(
                    "CREATE OR REPLACE FUNCTION reject_history_mutation() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'append-only history'; END $$"
                )
            )
            for operation in operations + ["truncate"]:
                name = f"{table}_no_{operation}"
                exists = connection.execute(
                    text("SELECT 1 FROM pg_trigger WHERE tgname = :name AND NOT tgisinternal"),
                    {"name": name},
                ).first()
                if not exists:
                    connection.execute(
                        text(
                            f"CREATE TRIGGER {name} BEFORE {operation.upper()} ON {table} "
                            "FOR EACH STATEMENT EXECUTE FUNCTION reject_history_mutation()"
                        )
                    )

    def import_legacy(self, legacy: Table) -> None:
        with self.engine.begin() as connection:
            # One import transaction and the same ledger lock as normal writers.
            connection.execute(select(self.head).where(self.head.c.id == 1).with_for_update())
            for row in connection.execute(
                select(legacy).order_by(legacy.c.timestamp, legacy.c.id)
            ).mappings():
                self.append(
                    connection,
                    row["run_id"],
                    row["actor"],
                    row["action"],
                    row["decision"],
                    row["detail"],
                    key=f"legacy:{row['id']}",
                    event_id=row["id"],
                    timestamp=row["timestamp"],
                    provenance="legacy_import",
                )
            self._protect(connection, "events", sealed=True)

    def append(
        self,
        connection: Connection,
        run_id: str,
        actor: str,
        action: str,
        decision: str,
        detail: str = "",
        *,
        key: str | None = None,
        event_id: str | None = None,
        timestamp: float | None = None,
        provenance: str = "native",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = key or str(uuid.uuid4())
        content = dict(
            run_id=run_id,
            actor=actor,
            action=action,
            decision=decision,
            detail=detail,
            provenance=provenance,
            data=data or {},
            model_mode="fixture",
        )
        head = (
            connection.execute(select(self.head).where(self.head.c.id == 1).with_for_update())
            .mappings()
            .one()
        )
        previous = (
            connection.execute(select(self.events).where(self.events.c.event_key == key))
            .mappings()
            .first()
        )
        if previous:
            if any(previous[field] != value for field, value in content.items()):
                raise JournalConflict("Conflicting reuse of an event identity")
            return dict(previous)
        event_id = event_id or identity(key)
        parent = ""
        if action != "run.create":
            parent = (
                connection.execute(
                    select(self.events.c.span_id)
                    .where(self.events.c.run_id == run_id, self.events.c.action == "run.create")
                    .order_by(self.events.c.sequence)
                    .limit(1)
                ).scalar_one_or_none()
                or ""
            )
        if (
            actor.startswith(("researcher-", "builder-", "reviewer-"))
            and action != "worker.started"
        ):
            worker_parent = connection.execute(
                select(self.events.c.span_id)
                .where(
                    self.events.c.run_id == run_id,
                    self.events.c.actor == actor,
                    self.events.c.action == "worker.started",
                )
                .order_by(self.events.c.sequence)
                .limit(1)
            ).scalar_one_or_none()
            parent = worker_parent or parent
        event = {
            **content,
            "sequence": head["sequence"] + 1,
            "event_id": event_id,
            "event_key": key,
            "timestamp": float(self.clock() if timestamp is None else timestamp),
            "trace_id": trace_id(run_id),
            "span_id": span_id(event_id),
            "parent_span_id": parent,
            "previous_hash": head["hash"],
        }
        event["hash"] = checksum(event)
        connection.execute(self.events.insert().values(**event))
        connection.execute(
            self.head.update()
            .where(self.head.c.id == 1)
            .values(sequence=event["sequence"], hash=event["hash"])
        )
        connection.execute(
            self.outbox.insert().values(
                sequence=event["sequence"], delivered=0, attempts=0, last_error=""
            )
        )
        return event

    def read(
        self, after: int = 0, limit: int = 200, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = select(self.events).where(self.events.c.sequence > after)
        if run_id:
            query = query.where(self.events.c.run_id == run_id)
        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    query.order_by(self.events.c.sequence).limit(limit)
                ).mappings()
            ]

    def verify(self, checkpoint: dict[str, Any] | None = None) -> dict[str, Any]:
        previous_hash = GENESIS
        count = 0
        anchor_seen = checkpoint is None or (
            checkpoint.get("checked") == 0 and checkpoint.get("head_hash") == GENESIS
        )
        valid = True
        with self.engine.connect() as connection:
            head = (
                connection.execute(
                    select(self.head).where(self.head.c.id == 1).with_for_update(read=True)
                )
                .mappings()
                .one()
            )
            for row in connection.execute(
                select(self.events)
                .where(self.events.c.sequence <= head["sequence"])
                .order_by(self.events.c.sequence)
            ).mappings():
                event = dict(row)
                stored_hash = event.pop("hash")
                count += 1
                if (
                    event["sequence"] != count
                    or event["previous_hash"] != previous_hash
                    or checksum(event) != stored_hash
                ):
                    valid = False
                previous_hash = stored_hash
                if checkpoint and checkpoint.get("checked") == count:
                    anchor_seen = checkpoint.get("head_hash") == stored_hash
            # Also detect rows beyond a manually rolled-back head.
            total = connection.execute(select(func.count()).select_from(self.events)).scalar_one()
        return {
            "valid": valid
            and anchor_seen
            and count == total == head["sequence"]
            and previous_hash == head["hash"],
            "checked": count,
            "head_hash": previous_hash,
        }

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    select(self.events)
                    .join(self.outbox, self.events.c.sequence == self.outbox.c.sequence)
                    .where(self.outbox.c.delivered == 0)
                    .order_by(self.events.c.sequence)
                    .limit(limit)
                ).mappings()
            ]

    def acknowledge(self, sequences: list[int], error: str | None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                self.outbox.update()
                .where(self.outbox.c.sequence.in_(sequences), self.outbox.c.delivered == 0)
                .values(
                    delivered=int(error is None),
                    attempts=self.outbox.c.attempts + 1,
                    last_error=error or "",
                )
            )

    def outbox_status(self) -> dict[str, Any]:
        with self.engine.connect() as connection:
            pending = connection.execute(
                select(func.count()).select_from(self.outbox).where(self.outbox.c.delivered == 0)
            ).scalar_one()
            error = connection.execute(
                select(self.outbox.c.last_error)
                .where(self.outbox.c.delivered == 0, self.outbox.c.last_error != "")
                .order_by(self.outbox.c.sequence.desc())
                .limit(1)
            ).scalar_one_or_none()
        return {"pending": pending, "last_error": error}

    def worker_started(self, run_id: str, actor: str) -> float | None:
        with self.engine.connect() as connection:
            return connection.execute(
                select(self.events.c.timestamp)
                .where(
                    self.events.c.run_id == run_id,
                    self.events.c.actor == actor,
                    self.events.c.action == "worker.started",
                )
                .limit(1)
            ).scalar_one_or_none()
