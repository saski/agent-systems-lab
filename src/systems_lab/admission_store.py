"""Durable FIFO admission. All mutations require the gateway's trusted owner."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, NoReturn

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    select,
)

if TYPE_CHECKING:
    from systems_lab.store import Store


class AdmissionStore:
    def __init__(self, store: Store, metadata: MetaData) -> None:
        self.store: Store = store
        self.batches: Table = Table(
            "admission_batches",
            metadata,
            Column("batch_id", String, primary_key=True),
            Column("scenario", JSON, nullable=False),
            Column("created_at", Float, nullable=False),
            Column("epoch", Integer, nullable=False),
            Column("owner", String, nullable=False),
            Column("events", JSON, nullable=False),
        )
        self.items: Table = Table(
            "admission_items",
            metadata,
            Column("item_id", String, primary_key=True),
            Column("batch_id", String, nullable=False),
            Column("position", Integer, nullable=False),
            Column("run_id", String, unique=True),
            Column("state", String, nullable=False),
            Column("outcome", String),
            Column("reason", String, nullable=False),
            UniqueConstraint("batch_id", "position"),
        )

    def _error(self, status: int, message: str) -> NoReturn:
        from systems_lab.store import ControlError

        raise ControlError(status, message)

    def _batch(self, connection: Any, batch_id: str) -> dict[str, Any]:
        row = (
            connection.execute(
                select(self.batches).where(self.batches.c.batch_id == batch_id).with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            self._error(404, "Unknown batch")
        return dict(row)

    def _items(self, connection: Any, batch_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in connection.execute(
                select(self.items)
                .where(self.items.c.batch_id == batch_id)
                .order_by(self.items.c.position)
            ).mappings()
        ]

    def _fence(self, connection: Any, batch_id: str, owner: str, epoch: int) -> dict[str, Any]:
        batch = self._batch(connection, batch_id)
        if batch["owner"] != owner or batch["epoch"] != epoch:
            self._error(409, "Stale admission owner")
        return batch

    def create(self, batch_id: str, scenario: dict[str, Any]) -> dict[str, Any]:
        # This slice deliberately supports the local SQLite gateway only.
        if self.store.engine.dialect.name != "sqlite":
            self._error(409, "Fixture admission requires the local SQLite gateway")
        with self.store.engine.begin() as connection:
            existing = (
                connection.execute(select(self.batches).where(self.batches.c.batch_id == batch_id))
                .mappings()
                .first()
            )
            if existing is not None:
                if existing["scenario"] != scenario:
                    self._error(409, "Batch identity already has another scenario")
            else:
                connection.execute(
                    self.batches.insert().values(
                        batch_id=batch_id,
                        scenario=scenario,
                        created_at=self.store.clock(),
                        epoch=0,
                        owner="",
                        events=[],
                    )
                )
                for position in range(2):
                    connection.execute(
                        self.items.insert().values(
                            item_id=str(uuid.uuid4()),
                            batch_id=batch_id,
                            position=position,
                            state="queued",
                            reason="",
                        )
                    )
        return self.snapshot(batch_id)

    def snapshot(self, batch_id: str) -> dict[str, Any]:
        with self.store.engine.connect().execution_options(lab_readonly=True) as connection:
            batch = self._batch(connection, batch_id)
            items = self._items(connection, batch_id)
        return {
            "batch_id": batch_id,
            "provenance": "fixture_workflow",
            "wip_limit": 1,
            "created_at": batch["created_at"],
            "scenario": batch["scenario"],
            "epoch": batch["epoch"],
            "items": items,
            "events": batch["events"],
            "wip": sum(item["state"] not in {"queued", "released"} for item in items),
            "complete": all(item["state"] == "released" for item in items),
        }

    def claim(self, batch_id: str, owner: str, expected_epoch: int) -> int:
        with self.store.engine.begin() as connection:
            batch = self._batch(connection, batch_id)
            if batch["owner"] == owner and batch["epoch"] == expected_epoch + 1:
                return batch["epoch"]
            updated = connection.execute(
                self.batches.update()
                .where(self.batches.c.batch_id == batch_id, self.batches.c.epoch == expected_epoch)
                .values(epoch=expected_epoch + 1, owner=owner)
            )
            if updated.rowcount != 1:
                self._error(409, "Admission ownership changed")
        return expected_epoch + 1

    def _transition(
        self,
        connection: Any,
        batch_id: str,
        item: dict[str, Any],
        state: str,
        *,
        reason: str = "",
        outcome: str | None = None,
    ) -> None:
        if item["state"] == state and item["reason"] == reason:
            return
        connection.execute(
            self.items.update()
            .where(self.items.c.item_id == item["item_id"])
            .values(state=state, reason=reason, outcome=outcome)
        )
        batch = self._batch(connection, batch_id)
        events = [
            *batch["events"],
            {
                "timestamp": self.store.clock(),
                "item_id": item["item_id"],
                "run_id": item["run_id"],
                "state": state,
                "reason": reason,
                "outcome": outcome,
            },
        ]
        connection.execute(
            self.batches.update().where(self.batches.c.batch_id == batch_id).values(events=events)
        )

    def reserve(self, batch_id: str, owner: str, epoch: int, item_id: str) -> str:
        with self.store.engine.begin() as connection:
            batch = self._fence(connection, batch_id, owner, epoch)
            items = self._items(connection, batch_id)
            item = next((item for item in items if item["item_id"] == item_id), None)
            if item is None:
                self._error(404, "Unknown batch item")
            if item["run_id"] is not None:
                return item["run_id"]
            next_item = next((item for item in items if item["state"] != "released"), None)
            if item != next_item or item["state"] != "queued":
                self._error(409, "The admitted place is occupied")
            run_id = self.store._create_run(connection, batch["scenario"])
            connection.execute(
                self.items.update()
                .where(self.items.c.item_id == item_id, self.items.c.run_id.is_(None))
                .values(run_id=run_id)
            )
            self._transition(connection, batch_id, {**item, "run_id": run_id}, "reserved")
            self.store._event(
                connection,
                run_id,
                "orchestrator",
                "batch.admit",
                "allow",
                data={"batch_id": batch_id, "item_id": item_id},
            )
        return run_id

    def transition(
        self,
        batch_id: str,
        owner: str,
        epoch: int,
        item_id: str,
        state: str,
        *,
        reason: str = "",
        reconciled: bool = False,
    ) -> None:
        """Called only while the coordinator holds the inherited process lock."""
        with self.store.engine.begin() as connection:
            self._fence(connection, batch_id, owner, epoch)
            item = next(
                (item for item in self._items(connection, batch_id) if item["item_id"] == item_id),
                None,
            )
            if item is None or item["run_id"] is None:
                self._error(409, "No admitted run")
            status = connection.execute(
                select(self.store.runs.c.status).where(self.store.runs.c.run_id == item["run_id"])
            ).scalar_one_or_none()
            if status is None:
                self._error(409, "Canonical run unavailable")
            if state == "launching":
                if item["state"] != "reserved" or status != "running":
                    self._error(409, "A launch cannot be repeated")
            elif state == "awaiting_review":
                if item["state"] != "launching" or status != "awaiting_review":
                    self._error(409, "Run is not awaiting review")
            elif state == "released":
                if status not in {"accepted", "rejected", "revoked"}:
                    self._error(409, "A canonical terminal outcome is required")
                if item["state"] in {"launching", "blocked"} and not reconciled:
                    self._error(409, "Explicit reconciliation required")
            elif state == "blocked":
                if item["state"] == "released":
                    self._error(409, "A released item cannot be re-admitted")
            else:
                self._error(422, "Unknown admission transition")
            self._transition(
                connection,
                batch_id,
                item,
                state,
                reason=reason,
                outcome=status if state == "released" else None,
            )
