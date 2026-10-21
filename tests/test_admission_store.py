import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from systems_lab.store import ControlError, Store
from tests.test_gateway import SCENARIO


def test_independent_connections_fence_owners_and_retry_the_same_binding(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'control.db'}"
    first, second = Store(url), Store(url)
    try:
        batch = first.admission.create(str(uuid.uuid4()), SCENARIO)
        batch_id = batch["batch_id"]
        barrier = Barrier(2)

        def compete(store: Store, owner: str) -> tuple[str, int | None]:
            barrier.wait(timeout=5)
            try:
                return owner, store.admission.claim(batch_id, owner, 0)
            except ControlError as error:
                assert error.status == 409
                return owner, None

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(compete, store, owner)
                for store, owner in ((first, "first"), (second, "second"))
            ]
            outcomes = [future.result(timeout=10) for future in futures]
        winners = [(owner, epoch) for owner, epoch in outcomes if epoch is not None]
        assert len(winners) == 1
        owner, epoch = winners[0]
        assert first.admission.claim(batch_id, owner, 0) == epoch
        item_id = batch["items"][0]["item_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(store.admission.reserve, batch_id, owner, epoch, item_id)
                for store in (first, second)
            ]
            runs = [future.result(timeout=10) for future in futures]
        assert runs[0] == runs[1]
        assert first.get_run(runs[0])["instances"] == []
        with pytest.raises(ControlError, match="occupied"):
            first.admission.reserve(batch_id, owner, epoch, batch["items"][1]["item_id"])
        with first.engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(first.runs)).scalar() == 1
        first.admission.transition(batch_id, owner, epoch, item_id, "launching")
        next_epoch = second.admission.claim(batch_id, "replacement", epoch)
        with pytest.raises(ControlError, match="Stale"):
            first.admission.transition(batch_id, owner, epoch, item_id, "blocked")
        first.revoke(runs[0])
        with pytest.raises(ControlError, match="reconciliation"):
            second.admission.transition(batch_id, "replacement", next_epoch, item_id, "released")
        assert second.admission.snapshot(batch_id)["wip"] == 1
    finally:
        first.close()
        second.close()


def test_run_creation_and_item_binding_roll_back_together(tmp_path: Path) -> None:
    store = Store(f"sqlite:///{tmp_path / 'control.db'}")
    try:
        batch = store.admission.create(str(uuid.uuid4()), SCENARIO)
        batch_id = batch["batch_id"]
        epoch = store.admission.claim(batch_id, "owner", 0)
        with store.engine.begin() as connection:
            connection.execute(
                text("""
                CREATE TRIGGER fail_binding BEFORE UPDATE OF run_id ON admission_items
                BEGIN SELECT RAISE(ABORT, 'binding unavailable'); END
            """)
            )
        with pytest.raises(IntegrityError, match="binding unavailable"):
            store.admission.reserve(batch_id, "owner", epoch, batch["items"][0]["item_id"])
        after = store.admission.snapshot(batch_id)
        assert after["wip"] == 0
        assert all(item["run_id"] is None for item in after["items"])
        with store.engine.connect() as connection:
            assert connection.execute(select(func.count()).select_from(store.runs)).scalar() == 0
        assert store.journal.verify()["checked"] == 0
    finally:
        store.close()
