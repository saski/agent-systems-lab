"""Historical facts survive retries, restarts, and collector outages."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError

from systems_lab.store import ControlError, Store
from tests.test_gateway import SCENARIO


def test_lifecycle_is_idempotent_after_restart_and_conflicting_reuse_fails(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'history.db'}"
    store = Store(url)
    run_id = store.create_run(SCENARIO)
    grant = store.issue_grant(run_id, "researcher", 120, 12)
    store.worker_event(run_id, grant["instance_id"], "started", "process")
    store.worker_event(run_id, grant["instance_id"], "completed", "process")
    before = store.journal.verify()
    store.close()
    store = Store(url)
    store.worker_event(run_id, grant["instance_id"], "completed", "process")
    assert store.journal.verify() == before
    with pytest.raises(ControlError, match="Conflicting"):
        store.worker_event(run_id, grant["instance_id"], "completed", "docker")
    assert store.journal.verify() == before
    store.revoke(run_id)
    revoked = store.journal.verify()
    store.revoke(run_id)
    assert store.journal.verify() == revoked
    store.close()


def test_sql_mutation_is_blocked_and_external_checkpoint_detects_privileged_rewrite(
    tmp_path: Path,
) -> None:
    store = Store(f"sqlite:///{tmp_path / 'history.db'}")
    run_id = store.create_run(SCENARIO)
    checkpoint = store.journal.verify()
    for statement in [
        "UPDATE journal SET decision='deny'",
        "DELETE FROM journal",
        "INSERT OR REPLACE INTO journal SELECT * FROM journal",
    ]:
        with pytest.raises(DatabaseError), store.engine.begin() as connection:
            connection.execute(text(statement))
    assert store.journal.verify() == checkpoint
    # A database owner can bypass triggers. An independently held head exposes that.
    with store.engine.begin() as connection:
        connection.execute(text("DROP TRIGGER journal_no_delete"))
        connection.execute(text("DELETE FROM journal"))
    assert not store.journal.verify()["valid"]
    assert not store.journal.verify(checkpoint)["valid"]
    assert run_id
    store.close()


def test_history_pagination_and_atomic_rollback(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'history.db'}")
    run_id = store.create_run(SCENARIO)
    grant = store.issue_grant(run_id, "researcher", 120, 12)
    store.authorize(grant["token"], "model.call")
    store.authorize(grant["token"], "model.call")
    events = store.journal.read(after=0, limit=2)
    assert [event["sequence"] for event in events] == [1, 2]
    rest = store.journal.read(after=events[-1]["sequence"])
    assert len(rest) == 2
    assert rest[0]["event_id"] != rest[1]["event_id"]
    assert len({event["trace_id"] for event in events + rest}) == 1
    before = store.journal.verify()
    with pytest.raises(RuntimeError), store.engine.begin() as connection:
        store.journal.append(connection, run_id, "gateway", "test.rollback", "record")
        raise RuntimeError("rollback")
    assert store.journal.verify() == before
    assert store.journal.outbox_status()["pending"] == 4
    store.close()


def test_concurrent_writers_get_contiguous_sequence_numbers(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'history.db'}"
    stores = [Store(url), Store(url)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda i: stores[i % 2].create_run(SCENARIO), range(12)))
    assert stores[0].journal.verify()["valid"]
    assert [event["sequence"] for event in stores[0].journal.read()] == list(range(1, 13))
    for store in stores:
        store.close()


def test_existing_history_is_preserved_and_labelled_once(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE events (id TEXT PRIMARY KEY, run_id TEXT, timestamp FLOAT, "
                "actor TEXT, action TEXT, decision TEXT, detail TEXT, model_mode TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO events VALUES ('old-event','old-run',1000,'operator',"
                "'run.create','allow','','fixture')"
            )
        )
    engine.dispose()
    store = Store(url)
    events = store.journal.read()
    assert len(events) == 1
    assert events[0]["event_id"] == "old-event"
    assert events[0]["timestamp"] == 1000
    assert events[0]["provenance"] == "legacy_import"
    before = store.journal.verify()
    store.close()
    store = Store(url)
    assert store.journal.verify() == before
    with pytest.raises(DatabaseError), store.engine.begin() as connection:
        connection.execute(text("DELETE FROM events"))
    assert "token" not in json.dumps(events)
    store.close()


def test_independent_checkpoint_detects_a_fully_rehashed_privileged_rewrite(tmp_path: Path) -> None:
    from sqlalchemy import select

    from systems_lab.journal import checksum

    store = Store(f"sqlite:///{tmp_path / 'rewrite.db'}")
    store.create_run(SCENARIO)
    checkpoint = store.journal.verify()
    with store.engine.begin() as connection:
        connection.execute(text("DROP TRIGGER journal_no_update"))
        original = dict(connection.execute(select(store.journal.events)).mappings().one())
        original.pop("hash")
        changed = {**original, "decision": "fabricated"}
        new_hash = checksum(changed)
        connection.execute(
            store.journal.events.update().values(decision="fabricated", hash=new_hash)
        )
        connection.execute(store.journal.head.update().values(hash=new_hash))
    assert store.journal.verify()["valid"]  # A hash chain alone cannot exclude its administrator.
    assert not store.journal.verify(checkpoint)["valid"]
    store.close()


def test_replacement_is_rejected_even_by_a_separate_sqlite_connection(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'replace.db'}"
    store = Store(url)
    store.create_run(SCENARIO)
    outsider = create_engine(url)
    with pytest.raises(DatabaseError), outsider.begin() as connection:
        connection.execute(text("INSERT OR REPLACE INTO journal SELECT * FROM journal"))
    assert store.journal.verify()["valid"]
    outsider.dispose()
    store.close()
