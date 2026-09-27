"""A deterministic stock-and-flow model for a task backlog."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Scenario:
    """Inputs for one discrete-time backlog simulation.

    Backlog and arrivals are measured in tasks; capacities are tasks per step.
    ``adjustment_gain`` is capacity change per task of observed backlog error.
    """

    steps: int
    initial_backlog: float
    arrivals_per_step: float
    initial_capacity: float
    base_capacity: float
    min_capacity: float
    max_capacity: float
    target_backlog: float
    observation_delay: int
    adjustment_gain: float

    def __post_init__(self) -> None:
        if isinstance(self.steps, bool) or not isinstance(self.steps, int):
            raise TypeError("steps must be an integer")
        if self.steps <= 0:
            raise ValueError("steps must be greater than zero")
        if isinstance(self.observation_delay, bool) or not isinstance(self.observation_delay, int):
            raise TypeError("observation_delay must be an integer")
        if self.observation_delay < 0:
            raise ValueError("observation_delay must be nonnegative")

        quantities = {
            "initial_backlog": self.initial_backlog,
            "arrivals_per_step": self.arrivals_per_step,
            "initial_capacity": self.initial_capacity,
            "base_capacity": self.base_capacity,
            "min_capacity": self.min_capacity,
            "max_capacity": self.max_capacity,
            "target_backlog": self.target_backlog,
            "adjustment_gain": self.adjustment_gain,
        }
        for name, value in quantities.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a number")
            try:
                finite = math.isfinite(float(value))
            except OverflowError:
                finite = False
            if not finite:
                raise ValueError(f"{name} must be finite")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")

        if self.min_capacity > self.max_capacity:
            raise ValueError("min_capacity must not exceed max_capacity")
        if not self.min_capacity <= self.initial_capacity <= self.max_capacity:
            raise ValueError("initial_capacity must be within capacity bounds")
        if not self.min_capacity <= self.base_capacity <= self.max_capacity:
            raise ValueError("base_capacity must be within capacity bounds")

    @classmethod
    def from_dict(cls, values: Mapping[str, object]) -> Scenario:
        """Build a scenario from a mapping with exactly the declared fields."""
        if not isinstance(values, Mapping):
            raise TypeError("scenario must be a mapping")
        if any(not isinstance(key, str) for key in values):
            raise ValueError("scenario field names must be strings")
        expected = set(cls.__dataclass_fields__)
        received = set(values)
        missing = sorted(expected - received)
        unknown = sorted(received - expected)
        if missing or unknown:
            details: list[str] = []
            if missing:
                details.append(f"missing fields: {', '.join(missing)}")
            if unknown:
                details.append(f"unknown fields: {', '.join(unknown)}")
            raise ValueError("; ".join(details))
        return cls(**dict(values))  # type: ignore[arg-type]


def _finite(value: float, name: str) -> float:
    try:
        finite_value = float(value)
    except OverflowError:
        finite_value = math.inf
    if not math.isfinite(finite_value):
        raise ValueError(f"simulation produced a non-finite {name}")
    return finite_value


def simulate(scenario: Scenario) -> dict[str, object]:
    """Run the scenario and return JSON-serializable observations and metrics.

    Each step observes the beginning backlog from ``observation_delay`` steps
    earlier (with the initial backlog used before enough history exists). The
    controller adjusts and bounds capacity, arrivals join the backlog, and
    processing removes at most the available work. The recorded backlog is the
    stock remaining at the end of that step.
    """
    if not isinstance(scenario, Scenario):
        raise TypeError("scenario must be a Scenario")

    backlog = float(scenario.initial_backlog)
    capacity = float(scenario.initial_capacity)
    backlog_history = [backlog]
    observations: list[dict[str, int | float]] = []
    backlog_max = backlog
    completed_total = 0.0
    capacity_changes = 0.0

    for step_index in range(scenario.steps):
        observed_index = max(0, step_index - scenario.observation_delay)
        observed_backlog = backlog_history[observed_index]
        capacity_start = capacity
        capacity_target = scenario.base_capacity + scenario.adjustment_gain * (
            observed_backlog - scenario.target_backlog
        )
        capacity = min(
            scenario.max_capacity,
            max(
                scenario.min_capacity,
                _finite(capacity_target, "capacity target"),
            ),
        )
        capacity_change = capacity - capacity_start

        backlog_start = backlog
        arrivals = float(scenario.arrivals_per_step)
        available_backlog = _finite(backlog_start + arrivals, "available backlog")
        completed = min(available_backlog, capacity)
        backlog = _finite(available_backlog - completed, "backlog")
        backlog_history.append(backlog)
        backlog_max = max(backlog_max, backlog)
        completed_total = _finite(completed_total + completed, "completed total")
        capacity_changes = _finite(capacity_changes + abs(capacity_change), "capacity changes")

        observations.append(
            {
                "step": step_index,
                "backlog_start": backlog_start,
                "observed_backlog": observed_backlog,
                "capacity_start": capacity_start,
                "capacity_change": capacity_change,
                "capacity": capacity,
                "arrivals": arrivals,
                "available_backlog": available_backlog,
                "completed": completed,
                "backlog_end": backlog,
            }
        )

    return {
        "model_version": "backlog-feedback-v1",
        "parameters": asdict(scenario),
        "observations": observations,
        "metrics": {
            "backlog_final": backlog,
            "backlog_max": backlog_max,
            "completed_total": completed_total,
            "capacity_changes": capacity_changes,
        },
    }
