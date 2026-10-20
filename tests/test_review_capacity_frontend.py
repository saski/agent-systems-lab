"""Run the browser projection tests against a real synthetic report."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from systems_lab.review_capacity import simulate

ROOT = Path(__file__).resolve().parents[1]
NODE_TEST = ROOT / "tests" / "frontend" / "review-capacity.test.cjs"


def fixed_scenario() -> dict[str, Any]:
    return {
        "model_version": "review-capacity-v1",
        "task_count": 24,
        "arrival_interval": 2,
        "execution_ticks": 8,
        "review_ticks": 6,
        "observation_horizon": 60,
        "drain_deadline": 500,
        "policies": [
            {"name": "A", "execution_slots": 1, "wip_limit": None},
            {"name": "B", "execution_slots": 4, "wip_limit": None},
            {"name": "C", "execution_slots": 4, "wip_limit": 3},
        ],
    }


def test_review_capacity_browser_projection(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the frontend projection tests")

    scenario = fixed_scenario()
    report_path = tmp_path / "attempt.json"
    zero_scenario = fixed_scenario()
    zero_scenario["observation_horizon"] = 0
    zero_scenario["drain_deadline"] = 1
    zero_report_path = tmp_path / "zero-horizon-attempt.json"

    def write_attempt(path: Path, inputs: dict[str, Any], attempt_id: str) -> None:
        path.write_text(
            json.dumps(
                {
                    "manifest": {
                        "schema_version": 1,
                        "experiment_type": "review-capacity",
                        "model_version": "review-capacity-v1",
                        "provenance": "synthetic_event_time_model",
                        "status": "complete",
                        "attempt_id": attempt_id,
                        "created_at": "2026-10-19T00:00:00Z",
                        "scenario_sha256": "a" * 64,
                        "report_sha256": "b" * 64,
                    },
                    "scenario": inputs,
                    "report": simulate(inputs),
                }
            ),
            encoding="utf-8",
        )

    write_attempt(report_path, scenario, "fixed-fixture")
    write_attempt(zero_report_path, zero_scenario, "zero-horizon-fixture")
    env = os.environ.copy()
    env["REVIEW_CAPACITY_TEST_REPORT"] = str(report_path)
    env["REVIEW_CAPACITY_ZERO_REPORT"] = str(zero_report_path)
    result = subprocess.run(
        [node, "--test", str(NODE_TEST)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
