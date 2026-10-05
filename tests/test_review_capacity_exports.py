"""Test review-capacity experiment export, read, and list functions."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from systems_lab.review_capacity_exports import export_attempt, list_attempts, read_attempt


@pytest.fixture
def attempts_root(tmp_path: Path) -> Path:
    """Trusted directory for review-capacity attempts."""
    root = tmp_path / "review_capacity_attempts"
    root.mkdir()
    return root


@pytest.fixture
def valid_scenario() -> dict[str, Any]:
    """Valid review-capacity-v1 scenario with exact fixture schema."""
    return {
        "model_version": "review-capacity-v1",
        "task_count": 2,
        "arrival_interval": 0,
        "execution_ticks": 2,
        "review_ticks": 3,
        "observation_horizon": 20,
        "drain_deadline": 50,
        "policies": [{"name": "A", "execution_slots": 1, "wip_limit": None}],
    }


def test_export_generates_fresh_uuid_hex(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Export without attempt_id generates fresh UUID hex."""
    manifest = export_attempt(attempts_root, valid_scenario)
    attempt_id = manifest["attempt_id"]
    assert isinstance(attempt_id, str) and len(attempt_id) == 32
    assert (attempts_root / attempt_id).is_dir()


def test_deterministic_report_actual_sha256(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Repeated export produces identical report bytes with actual SHA256."""
    m1 = export_attempt(attempts_root, valid_scenario)
    m2 = export_attempt(attempts_root, valid_scenario)
    assert m1["attempt_id"] != m2["attempt_id"]
    r1_bytes = (attempts_root / m1["attempt_id"] / "report.json").read_bytes()
    r2_bytes = (attempts_root / m2["attempt_id"] / "report.json").read_bytes()
    assert r1_bytes == r2_bytes
    actual_hash = hashlib.sha256(r1_bytes).hexdigest()
    assert m1["report_sha256"] == actual_hash
    assert m2["report_sha256"] == actual_hash


def test_scenario_bytehash_actual_sha256(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Scenario SHA256 is computed from actual bytes."""
    manifest = export_attempt(attempts_root, valid_scenario)
    scenario_bytes = (attempts_root / manifest["attempt_id"] / "scenario.json").read_bytes()
    actual_hash = hashlib.sha256(scenario_bytes).hexdigest()
    assert manifest["scenario_sha256"] == actual_hash


def test_explicit_id_reuse_comparing_original_bytes(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Explicit ID reuse raises FileExistsError preserving all original bytes."""
    export_attempt(attempts_root, valid_scenario, attempt_id="fixed")
    manifest_bytes = (attempts_root / "fixed" / "manifest.json").read_bytes()
    scenario_bytes = (attempts_root / "fixed" / "scenario.json").read_bytes()
    report_bytes = (attempts_root / "fixed" / "report.json").read_bytes()
    with pytest.raises(FileExistsError):
        export_attempt(attempts_root, valid_scenario, attempt_id="fixed")
    assert (attempts_root / "fixed" / "manifest.json").read_bytes() == manifest_bytes
    assert (attempts_root / "fixed" / "scenario.json").read_bytes() == scenario_bytes
    assert (attempts_root / "fixed" / "report.json").read_bytes() == report_bytes


@pytest.mark.parametrize(
    "invalid_id", [".", "..", "./outside", "../outside", "a/b", "%2F", "", "a" * 65]
)
def test_invalid_ids_raise_value_error(
    attempts_root: Path, valid_scenario: dict[str, Any], invalid_id: str
) -> None:
    """Invalid attempt IDs raise ValueError before file access."""
    with pytest.raises(ValueError):
        export_attempt(attempts_root, valid_scenario, attempt_id=invalid_id)
    assert not any(attempts_root.iterdir())


def test_roundtrip_exact_original_scenario(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Read returns exact original scenario bytes and manifest."""
    manifest = export_attempt(attempts_root, valid_scenario, attempt_id="rt")
    result = read_attempt(attempts_root, "rt")
    assert result["manifest"] == manifest
    assert result["scenario"] == valid_scenario
    assert isinstance(result["report"], dict)


def test_symlink_directory_rejected(attempts_root: Path, tmp_path: Path) -> None:
    """Symlink attempt directory is rejected."""
    real = tmp_path / "real"
    real.mkdir()
    (attempts_root / "link").symlink_to(real)
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "link")


def test_symlink_datafile_rejected(
    attempts_root: Path, valid_scenario: dict[str, Any], tmp_path: Path
) -> None:
    """Symlink data file is rejected."""
    export_attempt(attempts_root, valid_scenario, attempt_id="sd")
    external = tmp_path / "ext.json"
    external.write_text("{}")
    scenario_path = attempts_root / "sd" / "scenario.json"
    scenario_path.unlink()
    scenario_path.symlink_to(external)
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "sd")


def test_symlink_inside_trusted_root_rejected(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Symlink inside trusted root is rejected even when target resolves inside."""
    export_attempt(attempts_root, valid_scenario, attempt_id="real")
    (attempts_root / "alias").symlink_to(attempts_root / "real")
    manifest_path = attempts_root / "real" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["attempt_id"] = "alias"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "alias")


def test_oversized_manifest_rejected(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """Manifest over 16KiB raises ValueError."""
    export_attempt(attempts_root, valid_scenario, attempt_id="om")
    (attempts_root / "om" / "manifest.json").write_text('{"x":"' + ("y" * 17000) + '"}')
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "om")


def test_oversized_scenario_rejected(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """Scenario over 16KiB raises ValueError."""
    export_attempt(attempts_root, valid_scenario, attempt_id="os")
    (attempts_root / "os" / "scenario.json").write_text('{"x":"' + ("y" * 17000) + '"}')
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "os")


def test_oversized_report_rejected(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """Report over 5MiB raises ValueError."""
    export_attempt(attempts_root, valid_scenario, attempt_id="or")
    (attempts_root / "or" / "report.json").write_text(
        '{"x":"' + ("y" * (5 * 1024 * 1024 + 1000)) + '"}'
    )
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "or")


def test_corrupt_scenario_hash_rejected(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Altered scenario.json raises ValueError."""
    export_attempt(attempts_root, valid_scenario, attempt_id="cs")
    altered = valid_scenario.copy()
    altered["task_count"] = 999
    (attempts_root / "cs" / "scenario.json").write_text(json.dumps(altered))
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "cs")


def test_corrupt_report_hash_rejected(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """Altered report.json raises ValueError."""
    export_attempt(attempts_root, valid_scenario, attempt_id="cr")
    (attempts_root / "cr" / "report.json").write_text('{"fake":1}')
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "cr")


def test_corrupt_report_skipped_in_list(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """List skips attempts with corrupted report hash."""
    export_attempt(attempts_root, valid_scenario, attempt_id="good")
    export_attempt(attempts_root, valid_scenario, attempt_id="bad")
    (attempts_root / "bad" / "report.json").write_text('{"corrupted":1}')
    attempts = list_attempts(attempts_root)
    assert len(attempts) == 1
    assert attempts[0]["attempt_id"] == "good"


def test_incomplete_manifest_skipped(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """Incomplete attempt without manifest is skipped."""
    export_attempt(attempts_root, valid_scenario, attempt_id="ok")
    partial = attempts_root / "partial"
    partial.mkdir()
    (partial / "scenario.json").write_text("{}")
    attempts = list_attempts(attempts_root)
    assert len(attempts) == 1 and attempts[0]["attempt_id"] == "ok"


def test_malformed_manifest_skipped(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """Malformed manifest JSON is skipped."""
    export_attempt(attempts_root, valid_scenario, attempt_id="ok")
    broken = attempts_root / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text("not json")
    attempts = list_attempts(attempts_root)
    assert len(attempts) == 1


def test_symlink_attempt_skipped_in_list(
    attempts_root: Path, valid_scenario: dict[str, Any], tmp_path: Path
) -> None:
    """List skips symlinked attempt directories."""
    export_attempt(attempts_root, valid_scenario, attempt_id="good")
    real = tmp_path / "real"
    real.mkdir()
    (attempts_root / "link").symlink_to(real)
    attempts = list_attempts(attempts_root)
    assert len(attempts) == 1
    assert attempts[0]["attempt_id"] == "good"


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("status", "partial"),
        ("report_sha256", 12345),
        ("created_at", 999),
        ("unknown_extra_field", "unexpected"),
    ],
)
def test_strict_manifest_invalid_fields(
    attempts_root: Path, valid_scenario: dict[str, Any], field: str, value: Any
) -> None:
    """Read raises ValueError for invalid manifest fields; list skips them."""
    export_attempt(attempts_root, valid_scenario, attempt_id="strict")
    manifest_path = attempts_root / "strict" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest, indent=2))
    with pytest.raises(ValueError):
        read_attempt(attempts_root, "strict")
    attempts = list_attempts(attempts_root)
    assert len(attempts) == 0


def test_read_with_none_id_raises_value_error(attempts_root: Path) -> None:
    """read_attempt with None attempt_id raises ValueError."""
    with pytest.raises(ValueError):
        read_attempt(attempts_root, None)  # type: ignore[arg-type]


def test_list_max_50_attempts(attempts_root: Path, valid_scenario: dict[str, Any]) -> None:
    """List returns at most 50 valid manifests."""
    for i in range(60):
        export_attempt(attempts_root, valid_scenario, attempt_id=f"a{i:03d}")
    attempts = list_attempts(attempts_root)
    assert len(attempts) == 50


def test_list_missing_root_returns_empty(tmp_path: Path) -> None:
    """List returns empty when root does not exist."""
    assert list_attempts(tmp_path / "missing") == []


def test_read_missing_root_raises_value_error(tmp_path: Path) -> None:
    """Read raises ValueError when root does not exist."""
    with pytest.raises(ValueError):
        read_attempt(tmp_path / "missing", "any")


def test_incomplete_drain_with_complete_artifact(
    attempts_root: Path, valid_scenario: dict[str, Any]
) -> None:
    """Short horizon produces complete artifact status even if drain incomplete."""
    short = valid_scenario.copy()
    short["observation_horizon"] = 1
    short["drain_deadline"] = 1
    manifest = export_attempt(attempts_root, short, attempt_id="drain")
    assert manifest["status"] == "complete"
    result = read_attempt(attempts_root, "drain")
    assert result["report"]["policies"][0]["drain"]["complete"] is False
    assert result["manifest"]["status"] == "complete"


def test_cli_review_capacity_real_behavior(
    tmp_path: Path,
    valid_scenario: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI exports under LAB_ROOT/.lab/experiments/review-capacity/id."""
    lab_root = tmp_path / "lab"
    lab_root.mkdir()
    scenario_file = tmp_path / "scenario.json"
    scenario_file.write_text(json.dumps(valid_scenario))
    monkeypatch.setenv("LAB_ROOT", str(lab_root))
    monkeypatch.setattr(
        "sys.argv", ["cli", "experiment", "review-capacity", "--scenario", str(scenario_file)]
    )

    from systems_lab import cli

    cli.main()
    captured = capsys.readouterr()
    manifest = json.loads(captured.out)
    assert manifest["experiment_type"] == "review-capacity"
    assert manifest["status"] == "complete"
    attempt_id = manifest["attempt_id"]
    export_path = lab_root / ".lab" / "experiments" / "review-capacity" / attempt_id
    assert (export_path / "manifest.json").exists()
    assert (export_path / "scenario.json").exists()
    assert (export_path / "report.json").exists()
    assert not (lab_root / ".lab" / "control.db").exists()
    assert not (lab_root / ".lab" / "operator.token").exists()
