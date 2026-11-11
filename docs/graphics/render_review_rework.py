"""Render the fixed G02 comparison from verified local numerical evidence."""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name("review-rework")
sys.path.insert(0, str(ROOT / "src"))
from systems_lab.review_rework import simulate  # noqa: E402

FIFO = "#476889"
PRIORITY = "#ad532d"
EARLIER = "#20735d"


def read_evidence(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    report = json.loads(raw)
    report_hash = hashlib.sha256(raw).hexdigest()
    manifest = json.loads(path.with_name("manifest.json").read_text())
    scenario = json.loads((ROOT / "experiments/review-rework/scenario.json").read_text())
    if (
        manifest["experiment_type"] != "review-rework"
        or manifest["report_sha256"] != report_hash
        or report["inputs"] != scenario
        or report != simulate(scenario)
    ):
        raise ValueError("The figure requires a verified report of the fixed G02 scenario")
    return report, report_hash


def render(report: dict[str, Any], report_hash: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": report_hash,
        }
    )
    figure = plt.figure(figsize=(14, 9), facecolor="#faf9f6")
    layout = figure.add_gridspec(2, 2, width_ratios=[1, 1.05], hspace=0.6, wspace=0.35)
    per_task = figure.add_subplot(layout[:, 0])
    cumulative = figure.add_subplot(layout[0, 1])
    groups = figure.add_subplot(layout[1, 1])
    for axis in (per_task, cumulative, groups):
        axis.set_facecolor("#faf9f6")
        axis.set_axisbelow(True)

    figure.suptitle("G02 · What changes when corrections go first?", fontsize=21, x=0.07, ha="left")
    figure.text(
        0.07,
        0.925,
        "24 tasks · 6 fixed corrections · 4 execution slots · 1 reviewer · synthetic time",
        color="#51575c",
        fontsize=12,
    )

    deltas = report["comparison"]["tasks"]
    positions = list(range(len(deltas)))
    for position, task in zip(positions, deltas, strict=True):
        delta = task["turnaround_delta"]
        color = EARLIER if delta < 0 else PRIORITY
        per_task.barh(position, delta, color=color, height=0.65)
        if delta == 0:
            per_task.plot(0, position, "o", color="#7b8186", markersize=4)
        per_task.text(
            delta + (2 if delta >= 0 else -2),
            position,
            f"{delta:+d}" if delta else "0",
            va="center",
            ha="right" if delta < 0 else "left",
            fontsize=10,
        )
    per_task.set_yticks(
        positions,
        [f"{task['task_id'] + 1}{' *' if task['needs_correction'] else ''}" for task in deltas],
    )
    per_task.invert_yaxis()
    per_task.set_xlim(-105, 36)
    per_task.axvline(0, color="#747474", linewidth=0.8)
    per_task.grid(axis="x", alpha=0.18)
    per_task.set_title("Final acceptance: change for each task", loc="left", pad=14)
    per_task.set_ylabel("Task (* requires a correction)")
    per_task.set_xlabel("Ticks earlier (−) or later (+) than FIFO")

    for policy, color, label in zip(
        report["policies"], [FIFO, PRIORITY], ["FIFO", "Corrections first"], strict=True
    ):
        acceptance = sorted(task["accepted_tick"] for task in policy["tasks"])
        cumulative.step(
            [0, *acceptance],
            list(range(len(acceptance) + 1)),
            where="post",
            label=label,
            color=color,
            linewidth=2.3,
        )
        cumulative.scatter(acceptance[-1], 24, color=color, s=28)
    cumulative.set_title("Accepted tasks over time", loc="left", pad=14)
    cumulative.set_xlabel("Logical tick")
    cumulative.set_ylabel("Tasks accepted")
    cumulative.set_ylim(0, 26)
    cumulative.set_xlim(0, 200)
    cumulative.yaxis.set_major_locator(MaxNLocator(integer=True))
    cumulative.grid(alpha=0.18)
    cumulative.legend(frameon=False, loc="upper left")
    fifo, priority = report["policies"]
    cumulative.text(
        0,
        -0.36,
        f"Last acceptance: FIFO {fifo['drain']['tick']} · "
        f"Corrections first {priority['drain']['tick']}",
        transform=cumulative.transAxes,
        fontsize=11,
    )

    labels = ["Corrected (6)", "First-pass (18)", "All tasks (24)"]
    for index, (policy, color) in enumerate(zip(report["policies"], [FIFO, PRIORITY], strict=True)):
        metrics = policy["metrics"]
        values = [
            metrics["turnaround_by_group"][key]["mean"] for key in ("corrected", "first_pass")
        ]
        values.append(metrics["turnaround"]["mean"])
        bars = groups.barh(
            [i + (index - 0.5) * 0.34 for i in range(3)], values, height=0.3, color=color
        )
        groups.bar_label(bars, fmt="%.1f", padding=4, fontsize=11)
    groups.set_yticks(range(3), labels)
    groups.invert_yaxis()
    groups.set_xlim(0, 160)
    groups.set_xlabel("Mean ticks from arrival to acceptance")
    groups.set_title("Who benefits from the lower overall mean?", loc="left", pad=14)
    groups.grid(axis="x", alpha=0.18)

    earlier = sum(task["turnaround_delta"] < 0 for task in deltas)
    later = sum(task["turnaround_delta"] > 0 for task in deltas)
    unchanged = len(deltas) - earlier - later
    figure.text(
        0.07,
        0.035,
        f"Same work in both runs: {fifo['metrics']['execution_busy_ticks']} execution ticks "
        f"and {fifo['metrics']['review_busy_ticks']} review ticks. "
        f"{earlier} tasks finish earlier, {later} later, {unchanged} unchanged.\n"
        "Fixed, successful corrections; no measured quality, fatigue or real-team productivity.",
        fontsize=11,
        color="#51575c",
        linespacing=1.7,
    )
    figure.subplots_adjust(left=0.07, right=0.95, top=0.86, bottom=0.16)
    figure.savefig(OUTPUT / "comparison.png", dpi=160, facecolor=figure.get_facecolor())
    figure.savefig(
        OUTPUT / "comparison.svg", facecolor=figure.get_facecolor(), metadata={"Date": None}
    )
    svg = OUTPUT / "comparison.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    plt.close(figure)
    evidence = {
        "kind": "frozen_documentation_projection",
        "provenance": report["provenance"],
        "model_version": report["model_version"],
        "scenario_sha256": report["scenario_sha256"],
        "report_sha256": report_hash,
        "inputs": report["inputs"],
        "comparison": report["comparison"],
        "policies": [
            {key: policy[key] for key in ("name", "horizon", "drain", "metrics")}
            for policy in report["policies"]
        ],
    }
    (OUTPUT / "evidence.json").write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    print(OUTPUT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    render(*read_evidence(args.report))


if __name__ == "__main__":
    main()
