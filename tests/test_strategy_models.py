"""Tests for strategy_models — data-driven model fitting.

Covers thermal, warmup, degradation, and pit-profile models with
both sufficient-data and insufficient-data paths.
"""
from __future__ import annotations

import math
import pytest

from lap_coach_logger.core.strategy_models import (
    DegradationModel,
    LapObservation,
    PitMeasurement,
    PitProfile,
    StintLapSeries,
    ThermalModel,
    WarmupModel,
    fit_degradation_model,
    fit_pit_profile,
    fit_thermal_model,
    fit_warmup_model,
)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _cold_optimal_hot_laps() -> list[LapObservation]:
    """Synthesize laps with a clear thermal sweet-spot at 80-90 C.

    Cold laps (<80) get a penalty proportional to how far below 80.
    Hot laps (>90) get a penalty proportional to how far above 90.
    Optimal laps (80-90) have baseline pace (90 s).
    """
    laps: list[LapObservation] = []
    base = 90.0
    for temp in range(60, 75, 3):          # cold
        penalty = (80 - temp) * 0.05
        laps.append(LapObservation(avg_tyre_temp_c=float(temp), lap_time_s=base + penalty))
    for temp in range(80, 91, 2):          # optimal
        laps.append(LapObservation(avg_tyre_temp_c=float(temp), lap_time_s=base))
    for temp in range(95, 115, 4):         # hot
        penalty = (temp - 90) * 0.08
        laps.append(LapObservation(avg_tyre_temp_c=float(temp), lap_time_s=base + penalty))
    return laps


def _exponential_warmup_stints(n_stints: int = 4) -> list[StintLapSeries]:
    """Create stints where first few laps are slower (exponential warmup)."""
    stints: list[StintLapSeries] = []
    base = 90.0
    amplitude = 2.0     # 2 s penalty on lap 0
    decay = 0.7         # decay rate

    for _ in range(n_stints):
        laps: list[LapObservation] = []
        for i in range(12):
            penalty = amplitude * math.exp(-decay * i)
            laps.append(LapObservation(
                avg_tyre_temp_c=85.0,
                lap_time_s=base + penalty,
                stint_lap_index=i,
            ))
        stints.append(StintLapSeries(laps=laps))
    return stints


def _linear_degradation_laps(n: int = 20, rate: float = 0.002) -> list[LapObservation]:
    """Laps with linear pace degradation: pace = base * (1 + rate*lap)."""
    base = 90.0
    return [
        LapObservation(
            avg_tyre_temp_c=85.0,
            lap_time_s=base * (1.0 + rate * i),
            stint_lap_index=i,
        )
        for i in range(n)
    ]


def _cliff_degradation_laps(
    n: int = 25, rate: float = 0.001, cliff_lap: int = 15, cliff_rate: float = 0.005,
) -> list[LapObservation]:
    """Laps with linear degradation + quadratic cliff."""
    base = 90.0
    laps: list[LapObservation] = []
    for i in range(n):
        pace = 1.0 + rate * i
        if i >= cliff_lap:
            pace += cliff_rate * (i - cliff_lap) ** 2
        laps.append(LapObservation(
            avg_tyre_temp_c=85.0,
            lap_time_s=base * pace,
            stint_lap_index=i,
        ))
    return laps


# ===================================================================
#  Thermal Model
# ===================================================================

class TestThermalModelFit:
    def test_clear_optimal_window(self):
        laps = _cold_optimal_hot_laps()
        model = fit_thermal_model(laps)

        assert model is not None
        assert model.available is True
        assert model.sample_count == len(laps)

        # Optimal window should be discovered somewhere near 75-95 range
        assert model.optimal_temp_low < 85
        assert model.optimal_temp_high > 85

        # Slopes must be non-negative (penalties, not bonuses)
        assert model.cold_penalty_s_per_deg >= 0
        assert model.hot_penalty_s_per_deg >= 0

        # Penalty at cold temp should be positive
        assert model.predict_penalty(65.0) > 0.0

        # Penalty in the sweet-spot should be zero or near-zero
        assert model.predict_penalty(85.0) == pytest.approx(0.0, abs=0.01)

        # Penalty at hot temp should be positive
        assert model.predict_penalty(105.0) > 0.0

    def test_insufficient_data_returns_none(self):
        # Fewer than 5 laps
        laps = [LapObservation(avg_tyre_temp_c=80.0, lap_time_s=90.0) for _ in range(4)]
        assert fit_thermal_model(laps) is None

    def test_narrow_temp_range_returns_none(self):
        # Temp range < 5 C
        laps = [
            LapObservation(avg_tyre_temp_c=80.0 + i * 0.5, lap_time_s=90.0)
            for i in range(10)
        ]
        assert fit_thermal_model(laps) is None

    def test_roundtrip_dict(self):
        laps = _cold_optimal_hot_laps()
        model = fit_thermal_model(laps)
        assert model is not None

        d = model.to_dict()
        restored = ThermalModel.from_dict(d)
        assert restored.optimal_temp_low == pytest.approx(model.optimal_temp_low)
        assert restored.optimal_temp_high == pytest.approx(model.optimal_temp_high)
        assert restored.predict_penalty(70.0) == pytest.approx(model.predict_penalty(70.0))


# ===================================================================
#  Warmup Model
# ===================================================================

class TestWarmupModelFit:
    def test_exponential_warmup(self):
        stints = _exponential_warmup_stints(4)
        model = fit_warmup_model(stints)

        assert model is not None
        assert model.fitted is True
        assert model.sample_count == 4

        # First lap penalty should be near amplitude (2 s)
        p0 = model.predict_penalty(0)
        assert p0 > 1.0

        # Penalty should decay
        p5 = model.predict_penalty(5)
        assert p5 < p0

        # Late-stint penalty near zero
        p10 = model.predict_penalty(10)
        assert p10 < 0.3

    def test_insufficient_stints_returns_none(self):
        stints = _exponential_warmup_stints(2)
        assert fit_warmup_model(stints) is None

    def test_roundtrip_dict(self):
        stints = _exponential_warmup_stints(4)
        model = fit_warmup_model(stints)
        assert model is not None

        d = model.to_dict()
        restored = WarmupModel.from_dict(d)
        assert restored.amplitude_s == pytest.approx(model.amplitude_s)
        assert restored.predict_penalty(2) == pytest.approx(model.predict_penalty(2))


# ===================================================================
#  Degradation Model
# ===================================================================

class TestDegradationModelFit:
    def test_linear_degradation(self):
        laps = _linear_degradation_laps(20, rate=0.002)
        model = fit_degradation_model(laps)

        assert model is not None
        assert model.available is True
        assert model.sample_count == 20

        # Rate should be close to 0.002
        assert model.deg_rate_per_lap == pytest.approx(0.002, abs=0.001)

        # No cliff expected
        assert model.cliff_lap is None

        # predict_pace_factor at lap 0 should be ~1.0
        assert model.predict_pace_factor(0) == pytest.approx(1.0, abs=0.01)

        # predict_pace_factor at lap 10 should be ~1.02
        assert model.predict_pace_factor(10) == pytest.approx(1.02, abs=0.01)

    def test_degradation_with_cliff(self):
        laps = _cliff_degradation_laps(25, rate=0.001, cliff_lap=15, cliff_rate=0.005)
        model = fit_degradation_model(laps)

        assert model is not None
        assert model.available is True

        # Should detect a cliff somewhere near lap 15
        if model.cliff_lap is not None:
            assert 10 <= model.cliff_lap <= 20

        # Pace factor beyond cliff should be notably higher
        pf_10 = model.predict_pace_factor(10)
        pf_22 = model.predict_pace_factor(22)
        assert pf_22 > pf_10

    def test_insufficient_data_returns_none(self):
        laps = _linear_degradation_laps(9)
        assert fit_degradation_model(laps) is None

    def test_max_viable_stint(self):
        laps = _linear_degradation_laps(40, rate=0.003)
        model = fit_degradation_model(laps)
        assert model is not None
        # max_viable_stint is the lap where pace > 1.05
        # 1 + 0.003*lap > 1.05 => lap > 16.7 => lap ~17
        assert model.max_viable_stint is not None
        assert 14 <= model.max_viable_stint <= 20

    def test_roundtrip_dict(self):
        laps = _linear_degradation_laps(20, rate=0.002)
        model = fit_degradation_model(laps)
        assert model is not None

        d = model.to_dict()
        restored = DegradationModel.from_dict(d)
        assert restored.deg_rate_per_lap == pytest.approx(model.deg_rate_per_lap)
        assert restored.predict_pace_factor(5) == pytest.approx(model.predict_pace_factor(5))


# ===================================================================
#  Pit Profile
# ===================================================================

class TestPitProfileFit:
    def _make_measurements(self, n: int) -> list[PitMeasurement]:
        """Synthesize pit measurements.

        Model: total = 25 (transit) + 0.5 * fuel + 3.0 * tires_changed
        """
        import random
        random.seed(42)
        ms: list[PitMeasurement] = []
        for i in range(n):
            fuel = random.uniform(10, 50)
            tires = i % 2 == 0
            total = 25.0 + 0.5 * fuel + (3.0 if tires else 0.0) + random.gauss(0, 0.1)
            ms.append(PitMeasurement(
                total_time_s=total,
                fuel_added=fuel,
                tires_changed=tires,
                fuel_at_entry=10.0,
                fuel_at_exit=10.0 + fuel,
                compound_before="medium",
                compound_after="medium",
                recorded_at=float(i),
            ))
        return ms

    def test_two_plus_measurements(self):
        ms = self._make_measurements(8)
        profile = fit_pit_profile("monza", ms)

        assert profile.track == "monza"
        assert profile.beta_transit is not None
        assert profile.beta_fuel_rate is not None

        # Compute a cost
        cost = profile.compute_cost(30.0, True)
        assert cost is not None
        assert cost > 0

    def test_one_measurement(self):
        ms = self._make_measurements(1)
        profile = fit_pit_profile("spa", ms)

        assert profile.beta_transit is not None
        assert profile.beta_transit == pytest.approx(ms[0].total_time_s)
        assert profile.beta_fuel_rate is None

    def test_zero_measurements(self):
        profile = fit_pit_profile("nurburgring", [])

        assert profile.beta_transit is None
        assert profile.beta_fuel_rate is None
        assert profile.beta_tire_change is None
        assert profile.compute_cost(30.0, True) is None

    def test_roundtrip_dict(self):
        ms = self._make_measurements(6)
        profile = fit_pit_profile("suzuka", ms)

        d = profile.to_dict()
        restored = PitProfile.from_dict(d)
        assert restored.track == profile.track
        assert restored.beta_transit == pytest.approx(profile.beta_transit)


# ===================================================================
#  OLS helper (internal, but worth a sanity check)
# ===================================================================

class TestOlsSlopeIntercept:
    def test_perfect_line(self):
        from lap_coach_logger.core.strategy_models import _ols_slope_intercept

        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [3.0, 5.0, 7.0, 9.0, 11.0]  # y = 2x + 1
        slope, intercept, r2 = _ols_slope_intercept(xs, ys)

        assert slope == pytest.approx(2.0, abs=1e-6)
        assert intercept == pytest.approx(1.0, abs=1e-6)
        assert r2 == pytest.approx(1.0, abs=1e-6)

    def test_constant_returns_zero_slope(self):
        from lap_coach_logger.core.strategy_models import _ols_slope_intercept

        xs = [1.0, 2.0, 3.0]
        ys = [5.0, 5.0, 5.0]
        slope, intercept, r2 = _ols_slope_intercept(xs, ys)

        assert slope == pytest.approx(0.0, abs=1e-6)
        assert intercept == pytest.approx(5.0, abs=1e-6)
