import errno
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from systems_lab.gateway import create_app
from systems_lab.review_capacity_exports import export_attempt
from systems_lab.store import Store
from tests.test_gateway import ADMIN, SCENARIO
from tests.test_review_capacity import base_input

VIEWER = {"Authorization": "Bearer readonly-test-token"}
API = "/api/experiments/review-capacity"


@pytest.fixture
def reports_root(tmp_path: Path) -> Path:
    return tmp_path / ".lab" / "experiments" / "review-capacity"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    value = Store(f"sqlite:///{tmp_path / 'control.db'}")
    try:
        yield value
    finally:
        value.close()


@pytest.fixture
def client(store: Store, reports_root: Path) -> Iterator[TestClient]:
    app = create_app(
        store, "operator-test-token", "readonly-test-token", experiment_root=reports_root
    )
    with TestClient(app) as value:
        yield value


def test_viewer_can_list_and_read_verified_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".lab" / "experiments" / "review-capacity"
    scenario = base_input()
    manifest = export_attempt(root, scenario, "demo")
    store = Store(f"sqlite:///{tmp_path / 'control.db'}")
    try:
        with TestClient(create_app(store, "operator-test-token", "readonly-test-token")) as client:
            assert client.get(API).status_code == 401
            response = client.get(API, headers=VIEWER)
            assert response.status_code == 200
            assert response.json() == {"attempts": [manifest]}
            response = client.get(f"{API}/demo", headers=VIEWER)
            assert response.status_code == 200
            result = response.json()
            assert set(result) == {"manifest", "scenario", "report"}
            assert result["manifest"] == manifest
            assert result["scenario"] == scenario
            assert result["report"]["provenance"] == "synthetic_event_time_model"
            assert result["report"]["policies"][0]["drain"]["decided"] == 2
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["content-type"] == "application/json"
            assert client.get(API, headers=ADMIN).json() == {"attempts": [manifest]}
    finally:
        store.close()


def test_reports_reject_anonymous_invalid_and_worker_credentials(
    client: TestClient, reports_root: Path, store: Store
) -> None:
    export_attempt(reports_root, base_input(), "demo")
    run_id = store.create_run(SCENARIO)
    worker = store.issue_grant(run_id, "builder", 120, 12)
    for suffix in ("", "/demo"):
        for headers in (
            {},
            {"Authorization": "Bearer invalid"},
            {"Authorization": "Basic readonly-test-token"},
            {"Authorization": f"Bearer {worker['token']}"},
        ):
            assert client.get(f"{API}{suffix}", headers=headers).status_code == 401
        for headers in (VIEWER, ADMIN):
            assert client.get(f"{API}{suffix}", headers=headers).status_code == 200


def test_empty_reports_are_not_created_by_reads(client: TestClient, reports_root: Path) -> None:
    assert client.get(API, headers=VIEWER).json() == {"attempts": []}
    assert client.get(f"{API}/missing", headers=VIEWER).status_code == 404
    assert not reports_root.exists()


@pytest.mark.parametrize("filename", ["manifest.json", "scenario.json", "report.json"])
def test_altered_reports_are_rejected_and_excluded_from_listing(
    client: TestClient, reports_root: Path, filename: str
) -> None:
    manifest = export_attempt(reports_root, base_input(), "good")
    export_attempt(reports_root, base_input(), "altered")
    (reports_root / "altered" / filename).write_text("{}")
    response = client.get(f"{API}/altered", headers=VIEWER)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid experiment report"}
    assert client.get(API, headers=VIEWER).json() == {"attempts": [manifest]}


def test_incomplete_attempt_is_not_a_complete_report(
    client: TestClient, reports_root: Path
) -> None:
    export_attempt(reports_root, base_input(), "partial")
    (reports_root / "partial" / "manifest.json").unlink()
    assert client.get(f"{API}/partial", headers=VIEWER).status_code == 422
    assert client.get(API, headers=VIEWER).json() == {"attempts": []}


@pytest.mark.parametrize(
    "filename,size",
    [("manifest.json", 16385), ("scenario.json", 16385), ("report.json", 5242881)],
)
def test_oversized_reports_are_rejected(
    client: TestClient, reports_root: Path, filename: str, size: int
) -> None:
    export_attempt(reports_root, base_input(), "large")
    (reports_root / "large" / filename).write_bytes(b" " * size)
    assert client.get(f"{API}/large", headers=VIEWER).status_code == 422
    assert client.get(API, headers=VIEWER).json() == {"attempts": []}


@pytest.mark.parametrize(
    "attempt_id",
    ["%2e%2e", "%2e%2e%2foutside", "%252e%252e%252foutside", "a%5cb", "%00", "a" * 65],
)
def test_path_traversal_and_invalid_ids_cannot_read_outside_root(
    client: TestClient, tmp_path: Path, attempt_id: str
) -> None:
    export_attempt(tmp_path / "outside", base_input(), "secret")
    response = client.get(f"{API}/{attempt_id}", headers=VIEWER)
    assert response.status_code in (404, 422)
    assert "secret" not in response.text
    assert str(tmp_path) not in response.text


@pytest.mark.parametrize("filename", ["manifest.json", "scenario.json", "report.json"])
def test_symlinked_data_files_are_never_served(
    client: TestClient, reports_root: Path, tmp_path: Path, filename: str
) -> None:
    external = tmp_path / "outside"
    export_attempt(external, base_input(), "secret")
    export_attempt(reports_root, base_input(), "linked")
    path = reports_root / "linked" / filename
    path.unlink()
    path.symlink_to(external / "secret" / filename)
    assert client.get(f"{API}/linked", headers=VIEWER).status_code == 422
    assert client.get(API, headers=VIEWER).json() == {"attempts": []}


def test_symlinked_attempt_is_not_read_or_listed(
    client: TestClient, reports_root: Path, tmp_path: Path
) -> None:
    external = tmp_path / "outside"
    export_attempt(external, base_input(), "secret")
    reports_root.mkdir(parents=True)
    (reports_root / "secret").symlink_to(external / "secret", target_is_directory=True)
    assert client.get(f"{API}/secret", headers=VIEWER).status_code == 422
    assert client.get(API, headers=VIEWER).json() == {"attempts": []}


@pytest.mark.parametrize("link_parent", [False, True])
def test_symlinked_report_root_or_parent_is_rejected(
    store: Store, tmp_path: Path, link_parent: bool
) -> None:
    outside = tmp_path / "outside"
    export_attempt(outside / "reports", base_input(), "secret")
    link = tmp_path / "redirect"
    link.symlink_to(outside if link_parent else outside / "reports", target_is_directory=True)
    root = link / "reports" if link_parent else link
    app = create_app(store, "operator-test-token", "readonly-test-token", experiment_root=root)
    with TestClient(app) as client:
        for suffix in ("", "/secret"):
            response = client.get(f"{API}{suffix}", headers=VIEWER)
            assert response.status_code == 422
            assert str(outside) not in response.text


def test_unavailable_root_is_an_error_instead_of_an_empty_list(
    client: TestClient, reports_root: Path
) -> None:
    reports_root.parent.mkdir(parents=True)
    reports_root.write_text("not a directory")
    response = client.get(API, headers=VIEWER)
    assert response.status_code == 503
    assert response.json() == {"detail": "Experiment reports unavailable"}


def test_report_reads_and_rejected_writes_preserve_files_and_activity(
    client: TestClient, reports_root: Path, store: Store
) -> None:
    export_attempt(reports_root, base_input(), "demo")
    files = {path: path.read_bytes() for path in reports_root.rglob("*") if path.is_file()}
    history = store.journal.verify()
    activity = client.get("/api/activity", headers=VIEWER).json()
    for suffix in ("", "/demo"):
        assert client.get(f"{API}{suffix}", headers=VIEWER).status_code == 200
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert client.request(method, f"{API}{suffix}", headers=VIEWER).status_code == 405
    assert {path: path.read_bytes() for path in reports_root.rglob("*") if path.is_file()} == files
    assert store.journal.verify() == history
    current = client.get("/api/activity", headers=VIEWER).json()
    for key in ("cursor", "events", "runs", "integrity"):
        assert current[key] == activity[key]


def test_listing_and_loading_use_only_the_configured_root(
    client: TestClient, reports_root: Path, tmp_path: Path
) -> None:
    manifest = export_attempt(reports_root, base_input(), "local")
    outside = tmp_path / "outside"
    export_attempt(outside, base_input(), "secret")
    parameters = {"root": str(outside), "path": str(outside / "secret" / "report.json")}
    assert client.get(API, headers=VIEWER, params=parameters).json() == {"attempts": [manifest]}
    assert client.get(f"{API}/secret", headers=VIEWER, params=parameters).status_code == 404


def test_report_listing_is_bounded(client: TestClient, reports_root: Path) -> None:
    for index in range(51):
        export_attempt(reports_root, base_input(), f"attempt-{index}")
    response = client.get(API, headers=VIEWER)
    assert response.status_code == 200
    assert len(response.json()["attempts"]) == 50


@pytest.mark.parametrize(
    "error_type,error_number", [(PermissionError, errno.EACCES), (OSError, errno.EIO)]
)
def test_file_storage_failure_is_not_hidden_as_corruption_or_empty_data(
    client: TestClient,
    reports_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[OSError],
    error_number: int,
) -> None:
    export_attempt(reports_root, base_input(), "demo")
    report_file = reports_root / "demo" / "report.json"
    original_open = os.open

    def unavailable(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if path == report_file:
            raise error_type(error_number, "Storage failure")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", unavailable)
    for suffix in ("", "/demo"):
        response = client.get(f"{API}{suffix}", headers=VIEWER)
        assert response.status_code == 503
        assert response.json() == {"detail": "Experiment reports unavailable"}


def test_data_file_must_be_a_regular_file(client: TestClient, reports_root: Path) -> None:
    export_attempt(reports_root, base_input(), "demo")
    report_file = reports_root / "demo" / "report.json"
    report_file.unlink()
    report_file.mkdir()
    assert client.get(f"{API}/demo", headers=VIEWER).status_code == 422
    assert client.get(API, headers=VIEWER).json() == {"attempts": []}
