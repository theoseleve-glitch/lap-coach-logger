"""Self-vs-self consistency analysis.

Computes per-lap, per-sector, and per-corner consistency metrics
from telemetry data. No external dependencies beyond stdlib.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class ConsistencyReport:
    """Complete consistency analysis for a practice session."""
    overall_std_dev_s: float        # lap time std dev in seconds
    consistency_pct: float          # 0-100, higher = more consistent
    median_lap_time_s: float
    best_lap_time_s: float
    theoretical_best_s: float       # sum of best sectors
    per_sector_std_dev: list[float]  # std dev per sector
    worst_sector: int | None        # 0-indexed sector with highest variance
    worst_corners: list[dict]       # top 3 corners by variance [{name, std_dev_s}]
    trend: str                      # "improving" / "stable" / "degrading"
    focus_recommendation: str       # one actionable sentence
    lap_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_std_dev_s": round(self.overall_std_dev_s, 3),
            "consistency_pct": round(self.consistency_pct, 1),
            "median_lap_time_s": round(self.median_lap_time_s, 3),
            "best_lap_time_s": round(self.best_lap_time_s, 3),
            "theoretical_best_s": round(self.theoretical_best_s, 3),
            "per_sector_std_dev": [round(s, 3) for s in self.per_sector_std_dev],
            "worst_sector": self.worst_sector,
            "worst_corners": self.worst_corners,
            "trend": self.trend,
            "focus_recommendation": self.focus_recommendation,
            "lap_count": self.lap_count,
        }


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def analyze_consistency(
    lap_times: list[float],
    sector_times: list[list[float]] | None = None,
    corner_times: list[dict] | None = None,
) -> ConsistencyReport | None:
    """Analyze lap-time consistency for a practice session.

    Returns None if fewer than 3 laps are provided.
    """
    if len(lap_times) < 3:
        return None

    overall_std = _std_dev(lap_times)
    median_lap = _median(lap_times)
    best_lap = min(lap_times)

    # Consistency percentage: higher = more consistent
    if median_lap > 0:
        consistency_pct = max(0.0, min(100.0, 100.0 - (overall_std / median_lap * 100.0)))
    else:
        consistency_pct = 100.0

    # Sector analysis
    per_sector_std: list[float] = []
    worst_sector: int | None = None
    theoretical_best = best_lap

    if sector_times and len(sector_times) >= 2:
        num_sectors = len(sector_times[0])
        # Transpose: group by sector column
        sector_columns: list[list[float]] = [[] for _ in range(num_sectors)]
        for lap_sectors in sector_times:
            for i, t in enumerate(lap_sectors):
                if i < num_sectors:
                    sector_columns[i].append(t)

        per_sector_std = [_std_dev(col) for col in sector_columns]

        # Worst sector = highest std dev
        if per_sector_std:
            max_std = max(per_sector_std)
            worst_sector = per_sector_std.index(max_std)

        # Theoretical best = sum of best sector times
        theoretical_best = sum(min(col) for col in sector_columns)

    # Corner analysis
    worst_corners: list[dict] = []
    if corner_times:
        corner_stats = []
        for corner in corner_times:
            name = corner.get("name", "")
            times = corner.get("times", [])
            if len(times) >= 2:
                std = _std_dev(times)
                corner_stats.append({"name": name, "std_dev_s": round(std, 3)})
        # Sort by std_dev descending, take top 3
        corner_stats.sort(key=lambda c: c["std_dev_s"], reverse=True)
        worst_corners = corner_stats[:3]

    # Trend: compare std dev of last 5 vs first 5
    trend = "stable"
    if len(lap_times) >= 6:
        first_5 = lap_times[:5]
        last_5 = lap_times[-5:]
        std_first = _std_dev(first_5)
        std_last = _std_dev(last_5)
        if std_first > 0 and std_last < std_first:
            trend = "improving"
        elif std_first > 0 and std_last > std_first * 1.2:
            trend = "degrading"

    # Focus recommendation
    if worst_sector is not None:
        sector_label = worst_sector + 1
        sector_std = round(per_sector_std[worst_sector], 3)
        focus_recommendation = (
            f"Focus on Sector {sector_label} "
            f"\u2014 your most variable section (\u00b1{sector_std}s)"
        )
    elif worst_corners:
        corner_name = worst_corners[0]["name"]
        corner_std = worst_corners[0]["std_dev_s"]
        focus_recommendation = (
            f"Focus on {corner_name} "
            f"\u2014 highest variance (\u00b1{corner_std}s)"
        )
    else:
        focus_recommendation = (
            "Maintain current consistency, focus on reducing best lap gap"
        )

    return ConsistencyReport(
        overall_std_dev_s=overall_std,
        consistency_pct=consistency_pct,
        median_lap_time_s=median_lap,
        best_lap_time_s=best_lap,
        theoretical_best_s=theoretical_best,
        per_sector_std_dev=per_sector_std,
        worst_sector=worst_sector,
        worst_corners=worst_corners,
        trend=trend,
        focus_recommendation=focus_recommendation,
        lap_count=len(lap_times),
    )
