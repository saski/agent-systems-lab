"""Render documentation figures from a saved review-capacity report.

Matplotlib is a documentation-only dependency, outside the application lockfile.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name("review-capacity")
POLICY_COLORS = {"A": "#71829b", "B": "#3179b7", "C": "#21866b"}
STATES = [
    ("queued", "Admission queue", "#f1b779"),
    ("executing", "Executing", "#4f8acd"),
    ("awaiting_review", "Review queue", "#de703a"),
    ("reviewing", "Reviewing", "#a3cbe9"),
]


def state_at(policy: dict[str, Any], tick: int) -> dict[str, Any]:
    """Return the right-continuous post-transition state at a logical tick."""
    return next(sample for sample in reversed(policy["samples"]) if sample["tick"] <= tick)


def evidence_from(report_path: Path) -> dict[str, Any]:
    """Check the trace and retain a documentation projection, excluding runtime IDs."""
    raw = report_path.read_bytes()
    report = json.loads(raw)
    scenario = json.loads((ROOT / "experiments/review-capacity/scenario.json").read_text())
    if report["inputs"] != scenario or report["provenance"] != "synthetic_event_time_model":
        raise ValueError("The documentation requires the checked-in synthetic scenario")
    policies = report["policies"]
    if [policy["name"] for policy in policies] != ["A", "B", "C"]:
        raise ValueError("The comparison requires policies A, B and C")
    for policy in policies:
        for sample in policy["samples"]:
            occupied = sum(sample[field] for field, _, _ in STATES)
            if sample["arrived"] != occupied + sample["decided"]:
                raise ValueError("Trace fails task conservation")
            if sample["wip"] != occupied - sample["queued"]:
                raise ValueError("Trace fails admitted-WIP conservation")
            if sample["executing"] > policy["execution_slots"] or sample["reviewing"] > 1:
                raise ValueError("Trace exceeds service capacity")
            if policy["wip_limit"] is not None and sample["wip"] > policy["wip_limit"]:
                raise ValueError("Trace exceeds its WIP limit")
        for task in policy["tasks"]:
            milestones = [
                task[field]
                for field in (
                    "arrival_tick",
                    "admission_tick",
                    "ready_tick",
                    "review_start_tick",
                    "decision_tick",
                )
            ]
            if any(tick is None for tick in milestones) or milestones != sorted(milestones):
                raise ValueError("This guide requires a completely drained, ordered trace")
        snapshot = state_at(policy, scenario["observation_horizon"])
        if snapshot["decided"] != policy["horizon"]["decided"]:
            raise ValueError("Horizon summary differs from the trace")
    return {
        "kind": "frozen_documentation_projection",
        "model_version": report["model_version"],
        "provenance": report["provenance"],
        "report_sha256": hashlib.sha256(raw).hexdigest(),
        "scenario_sha256": report["scenario_sha256"],
        "inputs": report["inputs"],
        "policies": policies,
    }


def style_axis(axis: Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#d7dfe4")
    axis.tick_params(colors="#526170", length=0, pad=8)
    axis.grid(axis="y", color="#e5ebef", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))


def save_figure(figure: Any, name: str, description: str) -> None:
    with plt.rc_context({"svg.hashsalt": name, "svg.fonttype": "none"}):
        figure.savefig(
            OUTPUT / f"{name}.svg",
            metadata={"Date": None, "Creator": "Agent Systems Lab", "Description": description},
        )
    figure.savefig(
        OUTPUT / f"{name}.png",
        dpi=180,
        metadata={"Software": "Agent Systems Lab documentation", "Description": description},
    )
    plt.close(figure)


def comparison(evidence: dict[str, Any]) -> None:
    policies = evidence["policies"]
    horizon = evidence["inputs"]["observation_horizon"]
    figure, axes = plt.subplots(2, 1, figsize=(10, 8.2))
    figure.subplots_adjust(top=0.82, bottom=0.25, left=0.19, right=0.95, hspace=0.85)
    figure.suptitle(
        "More execution shifts the bottleneck",
        x=0.06,
        y=0.97,
        ha="left",
        fontsize=22,
        fontweight="bold",
        color="#172c3a",
    )
    figure.text(
        0.06,
        0.915,
        f"SYNTHETIC MODEL  /  tick {horizon}  /  24 arrived tasks  /  one reviewer",
        fontsize=10,
        color="#526170",
    )
    labels = ["A · 1 slot / no cap", "B · 4 slots / no cap", "C · 4 slots / WIP 3"]
    decided = [policy["horizon"]["decided"] for policy in policies]
    axes[0].barh(labels, decided, color=[POLICY_COLORS[p["name"]] for p in policies], height=0.55)
    for index, value in enumerate(decided):
        axes[0].text(
            value + 0.25,
            index,
            str(value),
            va="center",
            fontsize=14,
            fontweight="bold",
            color="#172c3a",
        )
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, max(decided) + 2)
    axes[0].set_xlabel("Simulated decisions completed by tick 60", color="#526170", labelpad=12)
    axes[0].set_title(
        "4× execution slots → 1.33× completed decisions",
        loc="left",
        pad=18,
        fontsize=14,
        fontweight="bold",
    )
    style_axis(axes[0])
    axes[0].grid(axis="x", color="#e5ebef")
    axes[0].grid(axis="y", visible=False)
    left = [0] * len(policies)
    for field, label, color in STATES:
        values = [state_at(policy, horizon)[field] for policy in policies]
        axes[1].barh(labels, values, left=left, color=color, height=0.6, label=label)
        for index, value in enumerate(values):
            if value:
                axes[1].text(
                    left[index] + value / 2,
                    index,
                    str(value),
                    ha="center",
                    va="center",
                    fontsize=11,
                    fontweight="bold",
                    color="#172c3a",
                )
        left = [start + value for start, value in zip(left, values, strict=True)]
    for index, count in enumerate(left):
        axes[1].text(count + 0.25, index, f"{count} pending", va="center", fontsize=10)
    axes[1].invert_yaxis()
    axes[1].set_xlim(0, 22)
    axes[1].set_xlabel("All pending tasks at tick 60, including admission waiting", labelpad=12)
    axes[1].set_title(
        "WIP changes where work waits", loc="left", pad=18, fontsize=14, fontweight="bold"
    )
    style_axis(axes[1])
    axes[1].xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    handles, labels = axes[1].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.55, 0.09),
        ncol=2,
        frameon=False,
        fontsize=10,
    )
    figure.text(
        0.06,
        0.025,
        "B → C: review queue 15 → 1, admission queue 0 → 13; total pending stays 16.\n"
        "Logical ticks are not elapsed seconds. This model accepts every reviewed task.",
        fontsize=10,
        color="#526170",
        linespacing=1.6,
    )
    save_figure(figure, "comparison", "Fixed-horizon decisions and all pending work by location.")


def trajectories(evidence: dict[str, Any]) -> None:
    policies = evidence["policies"]
    horizon = evidence["inputs"]["observation_horizon"]
    end = max(policy["drain"]["end_tick"] for policy in policies)
    fields = [
        ("decided", "Cumulative simulated decisions", "Tasks decided"),
        ("awaiting_review", "Queue 2 · waiting for review", "Tasks waiting"),
        ("queued", "Queue 1 · waiting for admission", "Tasks waiting"),
        ("wip", "Admitted work in progress", "Tasks inside WIP boundary"),
    ]
    figure, axes = plt.subplots(2, 2, figsize=(11, 8.2), sharex=True)
    figure.subplots_adjust(top=0.83, bottom=0.25, left=0.08, right=0.97, hspace=0.5, wspace=0.28)
    figure.suptitle(
        "Follow both queues through the full workload",
        x=0.06,
        y=0.97,
        ha="left",
        fontsize=21,
        fontweight="bold",
        color="#172c3a",
    )
    figure.text(
        0.06,
        0.915,
        "SYNTHETIC MODEL  /  dashed vertical line = common horizon, tick 60",
        fontsize=10,
        color="#526170",
    )
    for axis, (field, title, ylabel) in zip(axes.flat, fields, strict=True):
        for policy in policies:
            samples = [sample for sample in policy["samples"] if sample["tick"] <= end]
            ticks = [sample["tick"] for sample in samples]
            values = [sample[field] for sample in samples]
            if ticks[-1] < end:
                ticks.append(end)
                values.append(values[-1])
            axis.step(
                ticks,
                values,
                where="post",
                color=POLICY_COLORS[policy["name"]],
                linewidth=2.1,
                linestyle="--" if policy["name"] == "C" else "-",
                label=policy["name"],
            )
        axis.axvspan(0, horizon, color="#edf4f8", alpha=0.5)
        axis.axvline(horizon, color="#526170", linewidth=1, linestyle=":")
        axis.set_title(title, loc="left", fontweight="bold", fontsize=12, pad=14)
        axis.set_ylabel(ylabel, fontsize=10, color="#526170")
        axis.set_xlabel("Logical tick", fontsize=10, color="#526170")
        axis.set_xlim(0, end + 2)
        axis.set_ylim(bottom=0)
        style_axis(axis)
    axes[0, 0].text(
        0.4, 0.13, "B and C overlap", transform=axes[0, 0].transAxes, color="#526170", fontsize=10
    )
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.06),
        ncol=3,
        frameon=False,
        title="A · 1 slot     B · 4 slots     C · 4 slots / WIP 3",
    )
    figure.text(
        0.06,
        0.025,
        "Full drain: A = 198 ticks; B = C = 152 ticks. All 24 tasks finish.",
        fontsize=10,
        color="#526170",
    )
    save_figure(figure, "trajectories", "Post-transition states held until the next event.")


def build_explainer(evidence: dict[str, Any]) -> None:
    projection = {
        **evidence,
        "policies": [
            {key: value for key, value in policy.items() if key != "events"}
            for policy in evidence["policies"]
        ],
    }
    (OUTPUT / "evidence.json").write_text(json.dumps(projection, indent=2) + "\n")
    template = (OUTPUT / "explainer.template.html").read_text()
    template = template.replace("__EVIDENCE_JSON__", json.dumps(projection).replace("<", "\\u003c"))
    for name in ("flow", "comparison", "trajectories"):
        encoded = base64.b64encode((OUTPUT / f"{name}.svg").read_bytes()).decode()
        template = template.replace(
            f"__{name.upper()}_IMAGE__", f"data:image/svg+xml;base64,{encoded}"
        )
    (OUTPUT / "explainer.html").write_text(template)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Saved deterministic report.json")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
        }
    )
    evidence = evidence_from(args.report)
    comparison(evidence)
    trajectories(evidence)
    build_explainer(evidence)
    print(json.dumps({"output": str(OUTPUT), "report_sha256": evidence["report_sha256"]}))


if __name__ == "__main__":
    main()
