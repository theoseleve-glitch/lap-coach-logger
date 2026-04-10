"""Data-driven strategy model dataclasses and fitting functions.

Pure module -- no dependencies on other project modules.  All fitting
functions return ``None`` when the input data is insufficient.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


def _ols_slope_intercept(
    xs: list[float],
    ys: list[float],
) -> tuple[float, float, float]:
    """Ordinary-least-squares for *y = slope * x + intercept*.

    Returns ``(slope, intercept, r_squared)``.
    No numpy -- uses the normal equations directly.
    """
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0), 0.0

    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-15:
        return 0.0, sy / n, 0.0

    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n

    # R-squared
    y_mean = sy / n
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-15 else 0.0
    return slope, intercept, r_squared


def _median(values: list[float]) -> float:
    """Return the median of a sorted copy of *values*."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


@dataclass
class LapObservation:
    avg_tyre_temp_c: float
    lap_time_s: float
    stint_lap_index: int = 0
    fuel_level: float = 0.0


@dataclass
class StintLapSeries:
    laps: list[LapObservation] = field(default_factory=list)


@dataclass
class ThermalModel:
    optimal_temp_low: float
    optimal_temp_high: float
    cold_penalty_s_per_deg: float
    hot_penalty_s_per_deg: float
    r_squared: float
    sample_count: int
    available: bool

    def predict_penalty(self, temp_c: float) -> float:
        """Return the estimated time penalty (seconds) for *temp_c*."""
        if temp_c < self.optimal_temp_low:
            return self.cold_penalty_s_per_deg * (self.optimal_temp_low - temp_c)
        if temp_c > self.optimal_temp_high:
            return self.hot_penalty_s_per_deg * (temp_c - self.optimal_temp_high)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "optimal_temp_low": self.optimal_temp_low,
            "optimal_temp_high": self.optimal_temp_high,
            "cold_penalty_s_per_deg": self.cold_penalty_s_per_deg,
            "hot_penalty_s_per_deg": self.hot_penalty_s_per_deg,
            "r_squared": self.r_squared,
            "sample_count": self.sample_count,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ThermalModel:
        return cls(
            optimal_temp_low=d["optimal_temp_low"],
            optimal_temp_high=d["optimal_temp_high"],
            cold_penalty_s_per_deg=d["cold_penalty_s_per_deg"],
            hot_penalty_s_per_deg=d["hot_penalty_s_per_deg"],
            r_squared=d["r_squared"],
            sample_count=d["sample_count"],
            available=d["available"],
        )


@dataclass
class WarmupModel:
    amplitude_s: float
    decay_rate: float
    raw_penalties: list[float]
    fitted: bool
    sample_count: int

    def predict_penalty(self, stint_lap: int) -> float:
        """Return the warmup penalty for *stint_lap* (0-based)."""
        if self.fitted:
            return self.amplitude_s * math.exp(-self.decay_rate * stint_lap)
        # Unfitted: raw lookup, clamp to last known value
        if stint_lap < len(self.raw_penalties):
            return max(0.0, self.raw_penalties[stint_lap])
        return 0.0

    def to_dict(self) -> dict:
        return {
            "amplitude_s": self.amplitude_s,
            "decay_rate": self.decay_rate,
            "raw_penalties": list(self.raw_penalties),
            "fitted": self.fitted,
            "sample_count": self.sample_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WarmupModel:
        return cls(
            amplitude_s=d["amplitude_s"],
            decay_rate=d["decay_rate"],
            raw_penalties=list(d["raw_penalties"]),
            fitted=d["fitted"],
            sample_count=d["sample_count"],
        )


@dataclass
class DegradationModel:
    deg_rate_per_lap: float
    cliff_lap: Optional[int]
    cliff_rate: float
    max_viable_stint: Optional[int]
    r_squared: float
    sample_count: int
    available: bool

    def predict_pace_factor(self, stint_lap: int) -> float:
        """Return pace factor at *stint_lap* (1.0 = baseline)."""
        factor = 1.0 + self.deg_rate_per_lap * stint_lap
        if self.cliff_lap is not None and stint_lap >= self.cliff_lap:
            factor += self.cliff_rate * (stint_lap - self.cliff_lap) ** 2
        return factor

    def to_dict(self) -> dict:
        return {
            "deg_rate_per_lap": self.deg_rate_per_lap,
            "cliff_lap": self.cliff_lap,
            "cliff_rate": self.cliff_rate,
            "max_viable_stint": self.max_viable_stint,
            "r_squared": self.r_squared,
            "sample_count": self.sample_count,
            "available": self.available,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DegradationModel:
        return cls(
            deg_rate_per_lap=d["deg_rate_per_lap"],
            cliff_lap=d["cliff_lap"],
            cliff_rate=d["cliff_rate"],
            max_viable_stint=d["max_viable_stint"],
            r_squared=d["r_squared"],
            sample_count=d["sample_count"],
            available=d["available"],
        )


@dataclass
class PitMeasurement:
    total_time_s: float
    fuel_added: float
    tires_changed: bool
    fuel_at_entry: float
    fuel_at_exit: float
    compound_before: str
    compound_after: str
    recorded_at: float

    def to_dict(self) -> dict:
        return {
            "total_time_s": self.total_time_s,
            "fuel_added": self.fuel_added,
            "tires_changed": self.tires_changed,
            "fuel_at_entry": self.fuel_at_entry,
            "fuel_at_exit": self.fuel_at_exit,
            "compound_before": self.compound_before,
            "compound_after": self.compound_after,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PitMeasurement:
        return cls(
            total_time_s=d["total_time_s"],
            fuel_added=d["fuel_added"],
            tires_changed=d["tires_changed"],
            fuel_at_entry=d["fuel_at_entry"],
            fuel_at_exit=d["fuel_at_exit"],
            compound_before=d["compound_before"],
            compound_after=d["compound_after"],
            recorded_at=d["recorded_at"],
        )


@dataclass
class PitProfile:
    track: str
    beta_transit: Optional[float]
    beta_fuel_rate: Optional[float]
    beta_tire_change: Optional[float]
    r_squared: Optional[float]
    measurements: list[PitMeasurement] = field(default_factory=list)

    def compute_cost(
        self,
        fuel_to_add: float,
        changing_tires: bool,
    ) -> Optional[float]:
        """Estimate total pit-stop time, or ``None`` if no data."""
        if self.beta_transit is None:
            return None
        cost = self.beta_transit
        if self.beta_fuel_rate is not None:
            cost += self.beta_fuel_rate * fuel_to_add
        if changing_tires and self.beta_tire_change is not None:
            cost += self.beta_tire_change
        return cost

    def to_dict(self) -> dict:
        return {
            "track": self.track,
            "beta_transit": self.beta_transit,
            "beta_fuel_rate": self.beta_fuel_rate,
            "beta_tire_change": self.beta_tire_change,
            "r_squared": self.r_squared,
            "measurements": [m.to_dict() for m in self.measurements],
        }

    @classmethod
    def from_dict(cls, d: dict) -> PitProfile:
        return cls(
            track=d["track"],
            beta_transit=d["beta_transit"],
            beta_fuel_rate=d["beta_fuel_rate"],
            beta_tire_change=d["beta_tire_change"],
            r_squared=d["r_squared"],
            measurements=[PitMeasurement.from_dict(m) for m in d.get("measurements", [])],
        )


def fit_thermal_model(laps: list[LapObservation]) -> Optional[ThermalModel]:
    """Fit a thermal-window model from lap observations.

    Returns ``None`` if fewer than 5 laps or temperature range < 5 C.
    """
    if len(laps) < 5:
        return None

    temps = [lap.avg_tyre_temp_c for lap in laps]
    times = [lap.lap_time_s for lap in laps]

    t_min, t_max = min(temps), max(temps)
    if t_max - t_min < 5.0:
        return None

    median_time = _median(times)
    deltas = [t - median_time for t in times]

    # Grid search over (low, high) breakpoints
    step = max(1.0, (t_max - t_min) / 20.0)
    candidates: list[float] = []
    t = t_min
    while t <= t_max:
        candidates.append(t)
        t += step

    best_residual = float("inf")
    best_low = t_min
    best_high = t_max
    best_cold_slope = 0.0
    best_hot_slope = 0.0

    for i, low in enumerate(candidates):
        for high in candidates[i + 1:]:
            if high - low < 2.0:
                continue

            # Cold laps: temp < low
            cold_xs = [temp for temp in temps if temp < low]
            cold_ds = [deltas[j] for j, temp in enumerate(temps) if temp < low]
            # Hot laps: temp > high
            hot_xs = [temp for temp in temps if temp > high]
            hot_ds = [deltas[j] for j, temp in enumerate(temps) if temp > high]

            if not cold_xs and not hot_xs:
                continue

            # Fit cold slope (penalty per degree below low)
            cold_slope = 0.0
            cold_residual = 0.0
            if len(cold_xs) >= 2:
                # delta vs (low - temp) should have positive slope
                cold_gaps = [low - t for t in cold_xs]
                s, _i, _r = _ols_slope_intercept(cold_gaps, cold_ds)
                cold_slope = max(0.0, s)  # force non-negative
                cold_residual = sum(
                    (d - cold_slope * g) ** 2 for d, g in zip(cold_ds, cold_gaps)
                )
            elif cold_xs:
                cold_residual = sum(d ** 2 for d in cold_ds)

            # Fit hot slope (penalty per degree above high)
            hot_slope = 0.0
            hot_residual = 0.0
            if len(hot_xs) >= 2:
                hot_gaps = [t - high for t in hot_xs]
                s, _i, _r = _ols_slope_intercept(hot_gaps, hot_ds)
                hot_slope = max(0.0, s)
                hot_residual = sum(
                    (d - hot_slope * g) ** 2 for d, g in zip(hot_ds, hot_gaps)
                )
            elif hot_xs:
                hot_residual = sum(d ** 2 for d in hot_ds)

            # Optimal-zone residual
            opt_ds = [deltas[j] for j, temp in enumerate(temps) if low <= temp <= high]
            opt_residual = sum(d ** 2 for d in opt_ds)

            total_residual = cold_residual + hot_residual + opt_residual
            if total_residual < best_residual:
                best_residual = total_residual
                best_low = low
                best_high = high
                best_cold_slope = cold_slope
                best_hot_slope = hot_slope

    # Compute overall R-squared for the winning model
    ss_tot = sum(d ** 2 for d in deltas)
    r_sq = 1.0 - best_residual / ss_tot if ss_tot > 1e-15 else 0.0

    return ThermalModel(
        optimal_temp_low=best_low,
        optimal_temp_high=best_high,
        cold_penalty_s_per_deg=best_cold_slope,
        hot_penalty_s_per_deg=best_hot_slope,
        r_squared=r_sq,
        sample_count=len(laps),
        available=True,
    )


def fit_warmup_model(stints: list[StintLapSeries]) -> Optional[WarmupModel]:
    """Fit an exponential warmup model from multiple stints.

    Returns ``None`` if fewer than 3 stints.
    """
    if len(stints) < 3:
        return None

    # For each stint, compute steady-state and per-lap penalties
    max_lap = 0
    for stint in stints:
        for lap in stint.laps:
            if lap.stint_lap_index > max_lap:
                max_lap = lap.stint_lap_index

    # Accumulate penalties by stint_lap_index
    penalty_sums: dict[int, list[float]] = {}

    for stint in stints:
        times = [lap.lap_time_s for lap in stint.laps]
        # Steady-state = median of laps index 4+
        steady_laps = [lap.lap_time_s for lap in stint.laps if lap.stint_lap_index >= 4]
        if not steady_laps:
            steady_laps = times[-2:] if len(times) >= 2 else times
        steady_state = _median(steady_laps)

        for lap in stint.laps:
            penalty = lap.lap_time_s - steady_state
            idx = lap.stint_lap_index
            if idx not in penalty_sums:
                penalty_sums[idx] = []
            penalty_sums[idx].append(penalty)

    # Average penalties by index
    indices = sorted(penalty_sums.keys())
    raw_penalties = [
        sum(penalty_sums[i]) / len(penalty_sums[i]) for i in indices
    ]

    # Attempt log-linear OLS: log(penalty) = log(A) - k * lap
    # Only on positive penalties
    log_xs: list[float] = []
    log_ys: list[float] = []
    for i, idx in enumerate(indices):
        if raw_penalties[i] > 1e-6:
            log_xs.append(float(idx))
            log_ys.append(math.log(raw_penalties[i]))

    if len(log_xs) >= 2:
        neg_k, log_a, _ = _ols_slope_intercept(log_xs, log_ys)
        amplitude = math.exp(log_a)
        decay_rate = -neg_k  # slope is negative => decay is positive
        if decay_rate > 0 and amplitude > 0:
            return WarmupModel(
                amplitude_s=amplitude,
                decay_rate=decay_rate,
                raw_penalties=raw_penalties,
                fitted=True,
                sample_count=len(stints),
            )

    # Fallback: unfitted model with raw penalties
    return WarmupModel(
        amplitude_s=raw_penalties[0] if raw_penalties else 0.0,
        decay_rate=0.0,
        raw_penalties=raw_penalties,
        fitted=False,
        sample_count=len(stints),
    )


def fit_degradation_model(laps: list[LapObservation]) -> Optional[DegradationModel]:
    """Fit a degradation model from a single stint of lap observations.

    Returns ``None`` if fewer than 10 laps.
    """
    if len(laps) < 10:
        return None

    n = len(laps)
    times = [lap.lap_time_s for lap in laps]
    min_time = min(times)

    # Normalise: pace = lap_time / min_time
    paces = [t / min_time for t in times]
    xs = [float(i) for i in range(n)]

    # Linear fit: pace = 1 + rate * lap  =>  pace = intercept + slope * lap
    slope, intercept, r_sq_linear = _ols_slope_intercept(xs, paces)
    rate = max(0.0, slope)  # degradation only

    # Cliff search
    best_cliff_lap: Optional[int] = None
    best_cliff_rate = 0.0
    best_combined_r_sq = r_sq_linear

    # Residual sum for linear model
    ss_tot = sum((p - sum(paces) / n) ** 2 for p in paces)
    ss_res_linear = sum((paces[i] - (intercept + slope * i)) ** 2 for i in range(n))

    for cliff_candidate in range(5, n - 2):
        # Pre-cliff: linear fit on laps 0..cliff_candidate-1
        pre_xs = xs[:cliff_candidate]
        pre_ys = paces[:cliff_candidate]
        s_pre, i_pre, _ = _ols_slope_intercept(pre_xs, pre_ys)

        # Post-cliff: quadratic term on laps cliff_candidate..n-1
        # pace = i_pre + s_pre * lap + c_rate * (lap - cliff)^2
        # Fit c_rate via least-squares on residuals
        post_xs: list[float] = []
        post_residuals: list[float] = []
        for j in range(cliff_candidate, n):
            linear_pred = i_pre + s_pre * j
            residual = paces[j] - linear_pred
            gap_sq = float((j - cliff_candidate) ** 2)
            post_xs.append(gap_sq)
            post_residuals.append(residual)

        if len(post_xs) >= 2 and any(x > 0 for x in post_xs):
            c_rate_s, c_rate_i, _ = _ols_slope_intercept(post_xs, post_residuals)
            c_rate = max(0.0, c_rate_s)

            # Compute total residual
            ss_res = 0.0
            for j in range(n):
                pred = i_pre + s_pre * j
                if j >= cliff_candidate:
                    pred += c_rate * (j - cliff_candidate) ** 2
                ss_res += (paces[j] - pred) ** 2

            # Must beat linear by 15%
            if ss_res < ss_res_linear * 0.85:
                combined_r_sq = 1.0 - ss_res / ss_tot if ss_tot > 1e-15 else 0.0
                if combined_r_sq > best_combined_r_sq:
                    best_combined_r_sq = combined_r_sq
                    best_cliff_lap = cliff_candidate
                    best_cliff_rate = c_rate
                    rate = max(0.0, s_pre)  # use pre-cliff linear rate

    # max_viable_stint: first lap where pace > 1.05
    max_viable: Optional[int] = None
    for lap_idx in range(n * 2):  # search beyond observed data too
        pf = 1.0 + rate * lap_idx
        if best_cliff_lap is not None and lap_idx >= best_cliff_lap:
            pf += best_cliff_rate * (lap_idx - best_cliff_lap) ** 2
        if pf > 1.05:
            max_viable = lap_idx
            break

    return DegradationModel(
        deg_rate_per_lap=rate,
        cliff_lap=best_cliff_lap,
        cliff_rate=best_cliff_rate,
        max_viable_stint=max_viable,
        r_squared=best_combined_r_sq,
        sample_count=n,
        available=True,
    )


def fit_pit_profile(
    track: str,
    measurements: list[PitMeasurement],
) -> PitProfile:
    """Fit a pit-stop cost model from observed pit measurements.

    Always returns a ``PitProfile`` -- betas are ``None`` when data
    is insufficient.
    """
    if not measurements:
        return PitProfile(
            track=track,
            beta_transit=None,
            beta_fuel_rate=None,
            beta_tire_change=None,
            r_squared=None,
            measurements=list(measurements),
        )

    if len(measurements) == 1:
        return PitProfile(
            track=track,
            beta_transit=measurements[0].total_time_s,
            beta_fuel_rate=None,
            beta_tire_change=None,
            r_squared=None,
            measurements=list(measurements),
        )

    # 2+ measurements: OLS on fuel_added -> total_time
    fuels = [m.fuel_added for m in measurements]
    totals = [m.total_time_s for m in measurements]

    fuel_rate, transit, r_sq = _ols_slope_intercept(fuels, totals)

    # Estimate tire-change effect from residuals if variance exists
    tire_flags = [m.tires_changed for m in measurements]
    has_tire_variance = any(tire_flags) and not all(tire_flags)

    beta_tire: Optional[float] = None
    if has_tire_variance:
        # Compute residuals after fuel model
        residuals_with_tire: list[float] = []
        residuals_without_tire: list[float] = []
        for m in measurements:
            predicted = transit + fuel_rate * m.fuel_added
            residual = m.total_time_s - predicted
            if m.tires_changed:
                residuals_with_tire.append(residual)
            else:
                residuals_without_tire.append(residual)
        if residuals_with_tire and residuals_without_tire:
            avg_with = sum(residuals_with_tire) / len(residuals_with_tire)
            avg_without = sum(residuals_without_tire) / len(residuals_without_tire)
            beta_tire = avg_with - avg_without
            if beta_tire < 0:
                beta_tire = 0.0  # tire change shouldn't speed you up

    return PitProfile(
        track=track,
        beta_transit=transit,
        beta_fuel_rate=fuel_rate,
        beta_tire_change=beta_tire,
        r_squared=r_sq,
        measurements=list(measurements),
    )
