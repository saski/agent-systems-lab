import json

import pytest

from systems_lab.simulation import Scenario, simulate


def scenario_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "steps": 36,
        "initial_backlog": 10,
        "arrivals_per_step": 10,
        "initial_capacity": 4,
        "base_capacity": 10,
        "min_capacity": 0,
        "max_capacity": 20,
        "target_backlog": 8,
        "observation_delay": 0,
        "adjustment_gain": 0.4,
    }
    values.update(overrides)
    return values


def test_backlog_conservation_and_capacity_bounds_hold_for_every_step() -> None:
    result = simulate(Scenario.from_dict(scenario_values()))

    for step in result["observations"]:
        assert step["backlog_end"] == pytest.approx(
            step["backlog_start"] + step["arrivals"] - step["completed"]
        )
        assert 0 <= step["completed"] <= step["backlog_start"] + step["arrivals"]
        assert 0 <= step["capacity"] <= 20
        assert step["backlog_end"] >= 0

    assert result["metrics"]["backlog_final"] == result["observations"][-1]["backlog_end"]
    assert result["metrics"]["completed_total"] == pytest.approx(
        sum(step["completed"] for step in result["observations"])
    )
    json.dumps(result, allow_nan=False)


def test_longer_observation_delay_increases_peak_backlog_in_controlled_scenario() -> None:
    short_delay = simulate(Scenario.from_dict(scenario_values(observation_delay=0)))
    long_delay = simulate(Scenario.from_dict(scenario_values(observation_delay=4)))

    assert long_delay["metrics"]["backlog_max"] > short_delay["metrics"]["backlog_max"]
    assert long_delay["metrics"]["capacity_changes"] > short_delay["metrics"]["capacity_changes"]


def test_controller_saturates_at_maximum_without_exceeding_demand() -> None:
    result = simulate(
        Scenario.from_dict(
            scenario_values(
                steps=4,
                initial_backlog=100,
                arrivals_per_step=15,
                initial_capacity=5,
                adjustment_gain=1,
                max_capacity=12,
            )
        )
    )

    assert all(step["capacity"] == 12 for step in result["observations"])
    assert all(
        step["completed"] <= step["backlog_start"] + step["arrivals"]
        for step in result["observations"]
    )
    assert result["metrics"]["capacity_changes"] == pytest.approx(7)


@pytest.mark.parametrize(
    "override",
    [
        {"steps": True},
        {"steps": 0},
        {"observation_delay": 1.5},
        {"adjustment_gain": float("nan")},
        {"arrivals_per_step": -1},
        {"max_capacity": 3},
        {"extra": "ignored"},
    ],
)
def test_scenario_rejects_invalid_or_unknown_values(override: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        Scenario.from_dict(scenario_values(**override))


def test_scenario_requires_all_declared_fields() -> None:
    values = scenario_values()
    del values["target_backlog"]

    with pytest.raises(ValueError, match="target_backlog"):
        Scenario.from_dict(values)
