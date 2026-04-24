"""Canonical + source timestamps per ADR-007 (sprint T034).

Every telemetry sample in a v2 bundle carries:

* ``t_source_ns`` — nanoseconds since session start on the ORIGINAL
  sensor's clock (the "forensic" raw timestamp).
* ``t_canonical_ns`` — nanoseconds since session start in the
  session's canonical timebase, the one fusion uses downstream.

Desktop capture today reads one clock at a time (e.g. iRacing's SDK
tick, ACC's shared-memory frame counter), so the two values coincide.
When real-hardware fusion lands (phone + GPS + racebox), the canonical
value diverges; this helper still returns both so the contract stays
stable.
"""

from __future__ import annotations

from typing import Any, Iterable

from lap_coach_logger.core.schema import TelemetrySample


_DEFAULT_SOURCE_CLOCK = "device_monotonic"


def _to_ns(session_time_s: float | None) -> int:
    """Seconds → int nanoseconds, clamped to >= 0 per ADR-007 (ge=0)."""
    if session_time_s is None or session_time_s < 0:
        return 0
    return int(round(session_time_s * 1_000_000_000))


def derive_canonical_timestamps(
    samples: Iterable[TelemetrySample],
    *,
    source_clock: str = _DEFAULT_SOURCE_CLOCK,
) -> list[dict[str, Any]]:
    """Return ``[{t_source_ns, t_canonical_ns, t_source_clock}]`` per sample.

    The two ns values coincide today because desktop capture uses a
    single clock. Future fusion pipelines can replace this with a
    multi-source resolver that computes a distinct canonical timeline
    while keeping ``t_source_ns`` intact for forensic debugging.
    """
    rows: list[dict[str, Any]] = []
    for sample in samples:
        ns = _to_ns(sample.session_time_s)
        rows.append({
            "t_source_ns": ns,
            "t_canonical_ns": ns,
            "t_source_clock": source_clock,
        })
    return rows


__all__ = ["derive_canonical_timestamps"]
