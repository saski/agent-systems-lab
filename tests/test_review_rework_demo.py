"""Check the offline browser projection against the real numerical model."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from systems_lab.review_rework import simulate

ROOT = Path(__file__).resolve().parents[1]


def test_combined_demo_embeds_the_fixed_results_and_keeps_original_anchor() -> None:
    page = (ROOT / "docs/graphics/review-capacity/explainer.html").read_text()
    match = re.search(
        r'<script type="application/json" id="rework-evidence">(.*?)</script>', page, re.S
    )
    assert match is not None
    evidence = json.loads(match[1])
    scenario = json.loads((ROOT / "experiments/review-rework/scenario.json").read_text())
    report = simulate(scenario)
    assert evidence["inputs"] == scenario
    assert evidence["scenario_sha256"] == report["scenario_sha256"]
    assert evidence["comparison"] == report["comparison"]
    for saved, actual in zip(evidence["policies"], report["policies"], strict=True):
        assert saved == {key: actual[key] for key in saved}
    assert 'id="replay-section"' in page
    assert 'id="rework-section"' in page
    assert "__REWORK_" not in page


def test_review_rework_browser_projection(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser projection tests")
    scenario = json.loads((ROOT / "experiments/review-rework/scenario.json").read_text())
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(simulate(scenario)))
    result = subprocess.run(
        [node, "--test", str(ROOT / "tests/frontend/review-rework-demo.test.cjs")],
        env=os.environ | {"REVIEW_REWORK_REPORT": str(report_path)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
