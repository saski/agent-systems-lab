"""
Public API for persisting and loading review-capacity simulation attempts.

Each attempt is stored as a directory containing:
- scenario.json: input scenario
- report.json: simulation output
- manifest.json: metadata and integrity hashes (written last as completion marker)

All paths, IDs, and file contents are validated to prevent directory traversal,
symlink attacks, and data corruption.
"""

import hashlib
import json
import os
import re
import stat
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Any
from uuid import uuid4

from systems_lab.review_capacity import simulate

MAX_SCENARIO_BYTES = 16384
MAX_REPORT_BYTES = 5242880
ATTEMPT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


def _validate_attempt_id(attempt_id: Any) -> None:
    """Validate attempt ID format."""
    if not isinstance(attempt_id, str):
        raise ValueError(f"Attempt ID must be a string, got {type(attempt_id).__name__}")
    if not ATTEMPT_ID_PATTERN.fullmatch(attempt_id):
        raise ValueError(f"Invalid attempt ID format: {attempt_id}")


def _deterministic_json_bytes(obj: dict[str, Any]) -> bytes:
    """Serialize object to deterministic JSON bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_json_parse(data: bytes, filename: str) -> Any:
    """Parse JSON with strict validation: no NaN, no Infinity, no duplicate keys."""

    def check_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate key in JSON: {key}")
            result[key] = value
        return result

    def reject_special_floats(value: str) -> float:
        raise ValueError(f"JSON contains NaN or Infinity: {value}")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Invalid UTF-8 in {filename}") from e

    try:
        return json.loads(
            text,
            object_pairs_hook=check_duplicate_keys,
            parse_constant=reject_special_floats,
        )
    except (json.JSONDecodeError, ValueError, RecursionError) as e:
        raise ValueError(f"Invalid JSON in {filename}") from e


def _validate_root_directory(root: Path) -> Path:
    """Validate and resolve root directory, rejecting symlinks."""
    if root.is_symlink():
        raise ValueError(f"Attempt root must not be a symlink: {root}")
    resolved = root.resolve(strict=False)
    return resolved


def _validate_attempt_directory(root: Path, attempt_id: str) -> Path:
    """Validate attempt directory is within root and not a symlink."""
    resolved_root = root.resolve(strict=False)
    attempt_dir = root / attempt_id

    if attempt_dir.is_symlink():
        raise ValueError(f"Attempt directory must not be a symlink: {attempt_id}")

    resolved_attempt = attempt_dir.resolve(strict=False)

    try:
        resolved_attempt.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"Attempt directory escapes root: {attempt_id}") from error

    return attempt_dir


def _read_file_safe(path: Path, max_bytes: int, filename: str) -> bytes:
    """Read file with size limit and no symlink following."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise ValueError(f"Cannot open file (may be symlink or missing): {filename}") from error

    with os.fdopen(fd, "rb") as f:
        try:
            file_stat = os.fstat(f.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"Path is not a regular file: {filename}")
            if file_stat.st_size > max_bytes:
                raise ValueError(f"File exceeds size limit {max_bytes}: {filename}")

            data = f.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError(f"File exceeds size limit {max_bytes}: {filename}")
            return data
        except OSError as error:
            raise ValueError(f"Error reading file: {filename}") from error


def _write_file_exclusive(path: Path, data: bytes) -> None:
    """Write file exclusively with fsync, no overwrites."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError as error:
        raise ValueError(f"Cannot create exclusive file: {path}") from error

    with os.fdopen(fd, "wb") as f:
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except OSError as error:
            raise ValueError(f"Error writing file: {path}") from error


def _validate_manifest_structure(manifest: Any, attempt_id: str) -> None:
    """Validate manifest has exact required keys and value types."""
    required_keys = {
        "schema_version",
        "experiment_type",
        "model_version",
        "provenance",
        "status",
        "attempt_id",
        "created_at",
        "scenario_sha256",
        "report_sha256",
    }

    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a dict")

    if set(manifest.keys()) != required_keys:
        raise ValueError(
            f"Invalid manifest keys: expected {required_keys}, got {set(manifest.keys())}"
        )

    if not isinstance(manifest["schema_version"], int) or isinstance(
        manifest["schema_version"], bool
    ):
        raise ValueError(
            f"schema_version must be int, got {type(manifest['schema_version']).__name__}"
        )
    if manifest["schema_version"] != 1:
        raise ValueError(f"Invalid schema_version: {manifest['schema_version']}")

    if not isinstance(manifest["experiment_type"], str):
        raise ValueError("experiment_type must be str")
    if manifest["experiment_type"] != "review-capacity":
        raise ValueError(f"Invalid experiment_type: {manifest['experiment_type']}")

    if not isinstance(manifest["model_version"], str):
        raise ValueError("model_version must be str")
    if manifest["model_version"] != "review-capacity-v1":
        raise ValueError(f"Invalid model_version: {manifest['model_version']}")

    if not isinstance(manifest["provenance"], str):
        raise ValueError("provenance must be str")
    if manifest["provenance"] != "synthetic_event_time_model":
        raise ValueError(f"Invalid provenance: {manifest['provenance']}")

    if not isinstance(manifest["status"], str):
        raise ValueError("status must be str")
    if manifest["status"] != "complete":
        raise ValueError(f"Invalid status: {manifest['status']}")

    if not isinstance(manifest["attempt_id"], str):
        raise ValueError("attempt_id must be str")
    if manifest["attempt_id"] != attempt_id:
        raise ValueError(f"Manifest attempt_id mismatch: {manifest['attempt_id']} != {attempt_id}")

    if not isinstance(manifest["scenario_sha256"], str):
        raise ValueError("scenario_sha256 must be str")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest["scenario_sha256"]):
        raise ValueError("Invalid scenario_sha256 format")

    if not isinstance(manifest["report_sha256"], str):
        raise ValueError("report_sha256 must be str")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest["report_sha256"]):
        raise ValueError("Invalid report_sha256 format")

    if not isinstance(manifest["created_at"], str):
        raise ValueError("created_at must be str")
    try:
        parsed = datetime.fromisoformat(manifest["created_at"].replace("Z", "+00:00"))
        if parsed.tzinfo != UTC:
            raise ValueError("Timestamp must be UTC")
        if not manifest["created_at"].endswith("Z"):
            raise ValueError("Timestamp must end with Z")
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid created_at timestamp: {e}") from e


def export_attempt(
    root: Path,
    scenario: dict[str, Any],
    attempt_id: str | None = None,
) -> dict[str, Any]:
    """
    Export a review-capacity simulation attempt to immutable storage.

    Validates scenario, runs simulation, and writes scenario.json, report.json,
    and manifest.json (completion marker) to an exclusive directory.

    Args:
        root: Trusted root directory for attempts
        scenario: Input scenario dict
        attempt_id: Optional ID (default: random hex); must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}

    Returns:
        Manifest dict with schema_version, experiment_type, model_version, provenance,
        status, attempt_id, created_at, scenario_sha256, report_sha256

    Raises:
        ValueError: Invalid ID, oversized data, simulation failure, or filesystem conflict
    """
    if attempt_id is None:
        attempt_id = uuid4().hex

    _validate_attempt_id(attempt_id)

    report = simulate(scenario)

    scenario_bytes = _deterministic_json_bytes(scenario)
    report_bytes = _deterministic_json_bytes(report)

    if len(scenario_bytes) > MAX_SCENARIO_BYTES:
        raise ValueError(f"Scenario exceeds {MAX_SCENARIO_BYTES} bytes")
    if len(report_bytes) > MAX_REPORT_BYTES:
        raise ValueError(f"Report exceeds {MAX_REPORT_BYTES} bytes")

    scenario_hash = hashlib.sha256(scenario_bytes).hexdigest()
    report_hash = hashlib.sha256(report_bytes).hexdigest()

    root.mkdir(parents=True, exist_ok=True)
    validated_root = _validate_root_directory(root)
    attempt_dir = validated_root / attempt_id

    try:
        attempt_dir.mkdir(exist_ok=False)
    except FileExistsError as e:
        raise e

    try:
        _write_file_exclusive(attempt_dir / "scenario.json", scenario_bytes)
        _write_file_exclusive(attempt_dir / "report.json", report_bytes)

        manifest: dict[str, Any] = {
            "schema_version": 1,
            "experiment_type": "review-capacity",
            "model_version": "review-capacity-v1",
            "provenance": "synthetic_event_time_model",
            "status": "complete",
            "attempt_id": attempt_id,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "scenario_sha256": scenario_hash,
            "report_sha256": report_hash,
        }

        manifest_bytes = _deterministic_json_bytes(manifest)
        _write_file_exclusive(attempt_dir / "manifest.json", manifest_bytes)

        return manifest
    except Exception:
        raise


def read_attempt(root: Path, attempt_id: str) -> dict[str, Any]:
    """
    Read and validate a stored attempt.

    Args:
        root: Trusted root directory for attempts
        attempt_id: Attempt identifier

    Returns:
        Dict with keys: manifest, scenario, report

    Raises:
        ValueError: Invalid ID, missing/corrupt data, integrity failure
    """
    _validate_attempt_id(attempt_id)

    validated_root = _validate_root_directory(root)
    attempt_dir = _validate_attempt_directory(validated_root, attempt_id)

    if not attempt_dir.exists():
        raise ValueError(f"Attempt not found: {attempt_id}")
    if not attempt_dir.is_dir():
        raise ValueError(f"Attempt path is not a directory: {attempt_id}")

    manifest_bytes = _read_file_safe(
        attempt_dir / "manifest.json", MAX_SCENARIO_BYTES, "manifest.json"
    )
    manifest = _strict_json_parse(manifest_bytes, "manifest.json")
    _validate_manifest_structure(manifest, attempt_id)

    scenario_bytes = _read_file_safe(
        attempt_dir / "scenario.json", MAX_SCENARIO_BYTES, "scenario.json"
    )
    scenario = _strict_json_parse(scenario_bytes, "scenario.json")

    report_bytes = _read_file_safe(attempt_dir / "report.json", MAX_REPORT_BYTES, "report.json")
    report = _strict_json_parse(report_bytes, "report.json")

    scenario_hash = hashlib.sha256(scenario_bytes).hexdigest()
    if scenario_hash != manifest["scenario_sha256"]:
        raise ValueError("Scenario hash mismatch")

    report_hash = hashlib.sha256(report_bytes).hexdigest()
    if report_hash != manifest["report_sha256"]:
        raise ValueError("Report hash mismatch")

    if not isinstance(scenario, dict):
        raise ValueError("Scenario must be a dict")
    if not isinstance(report, dict):
        raise ValueError("Report must be a dict")

    if report.get("model_version") != manifest["model_version"]:
        raise ValueError("Report model_version mismatch")
    if report.get("provenance") != manifest["provenance"]:
        raise ValueError("Report provenance mismatch")
    if report.get("inputs") != scenario:
        raise ValueError("Report inputs do not match scenario")

    simulate(scenario)

    return {
        "manifest": manifest,
        "scenario": scenario,
        "report": report,
    }


def list_attempts(root: Path) -> list[dict[str, Any]]:
    """
    List valid attempts in root directory.

    Scans up to 200 directory entries and returns up to 50 valid manifests
    after full validation (hashes, bounds, structure).

    Args:
        root: Trusted root directory for attempts

    Returns:
        List of manifest dicts

    Raises:
        ValueError: Root is a symlink
    """
    if not root.exists():
        return []

    if root.is_symlink():
        raise ValueError(f"Attempt root must not be a symlink: {root}")

    results: list[dict[str, Any]] = []

    try:
        with os.scandir(root) as entries:
            for entry in islice(entries, 200):
                if len(results) >= 50:
                    break

                if not entry.is_dir(follow_symlinks=False):
                    continue

                attempt_id = entry.name

                try:
                    _validate_attempt_id(attempt_id)
                    result = read_attempt(root, attempt_id)
                    results.append(result["manifest"])
                except ValueError:
                    continue
    except OSError:
        return []

    return results
