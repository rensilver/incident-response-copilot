import pytest

from incident_copilot.demo.curves import time_grid, value_at
from incident_copilot.demo.scenarios import MetricShape


def test_time_grid_is_ascending_epoch_seconds_ending_in_the_past() -> None:
    grid = time_grid(hours=2, step_seconds=60)
    assert len(grid) == 120
    assert grid == sorted(grid)
    assert all(isinstance(t, int) for t in grid)


def test_time_grid_step_is_honoured() -> None:
    grid = time_grid(hours=1, step_seconds=30)
    assert grid[1] - grid[0] == 30


def test_steady_ignores_progress() -> None:
    assert value_at(MetricShape.STEADY, 5.0, 99.0, 0.9, 0.5) == 5.0


def test_ramp_is_flat_before_anomaly_start() -> None:
    assert value_at(MetricShape.RAMP, 1.0, 5.0, 0.2, 0.5) == 1.0


def test_ramp_reaches_peak_at_end() -> None:
    assert value_at(MetricShape.RAMP, 1.0, 5.0, 1.0, 0.5) == pytest.approx(5.0)


def test_ramp_is_monotonic_after_anomaly_start() -> None:
    values = [value_at(MetricShape.RAMP, 1.0, 5.0, p / 100, 0.5) for p in range(101)]
    assert values == sorted(values)


def test_step_jumps_at_anomaly_start() -> None:
    assert value_at(MetricShape.STEP, 0.0, 0.15, 0.59, 0.6) == 0.0
    assert value_at(MetricShape.STEP, 0.0, 0.15, 0.61, 0.6) == pytest.approx(0.15)


def test_sawtooth_resets_and_stays_within_bounds() -> None:
    values = [value_at(MetricShape.SAWTOOTH, 380.0, 1900.0, p / 200, 0.1) for p in range(201)]
    assert min(values) >= 380.0
    assert max(values) <= 1900.0
    # a reset means at least one point drops relative to its predecessor
    assert any(b < a for a, b in zip(values, values[1:], strict=True))
