"""T121: Mode-driven overlay preset model.

Per spec — "preset = list of widget ids + positions". Frozen
dataclasses so the runtime can hash + share instances without
defensive copies; tuple of placements rather than list so the
preset is truly immutable post-construction.

Distinct from :class:`overlays.models.OverlayPreset` (the
user-editable layout system with filters/scopes/slot bindings):
this lighter model is what the :class:`Mode.overlay_preset_id`
contract resolves at runtime — every Mode (T107-T110) maps to
exactly one of these. T122-T125 will define the four canonical
instances (race-minimal / practice / endurance / streamer).

Position model is ``(x, y, width, height)`` in floats; T121
doesn't prescribe units — the renderer can interpret them as
normalised (0..1) or absolute pixels. That's a runtime concern;
the model is dumb storage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class WidgetPlacement:
    """One widget's position within a :class:`ModeOverlayPreset`."""

    widget_id: str
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WidgetPlacement:
        return cls(
            widget_id=str(payload["widget_id"]),
            x=float(payload["x"]),
            y=float(payload["y"]),
            width=float(payload["width"]),
            height=float(payload["height"]),
        )


@dataclass(frozen=True, slots=True)
class ModeOverlayPreset:
    """A mode's static widget set: id + list of placements.

    T134: ``version`` tracks edit iterations of a given preset_id.
    Distinct from T132's ``schema_version`` envelope (the wire
    format) — this is *content* version. Bumped on every edit so
    a user's local copy can be compared against an exported one
    to detect drift.
    """

    preset_id: str
    widgets: tuple[WidgetPlacement, ...] = field(default_factory=tuple)
    version: int = 1

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for placement in self.widgets:
            if placement.widget_id in seen:
                raise ValueError(
                    f"duplicate widget id {placement.widget_id!r} "
                    f"in preset {self.preset_id!r}"
                )
            seen.add(placement.widget_id)

    def get_placement(self, widget_id: str) -> WidgetPlacement | None:
        for placement in self.widgets:
            if placement.widget_id == widget_id:
                return placement
        return None

    def bumped(self) -> ModeOverlayPreset:
        """Return a copy with ``version + 1``. Frozen-dataclass-
        safe — the original instance is left untouched."""
        return ModeOverlayPreset(
            preset_id=self.preset_id,
            widgets=self.widgets,
            version=self.version + 1,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "widgets": [w.to_dict() for w in self.widgets],
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModeOverlayPreset:
        widgets_raw = payload.get("widgets") or ()
        widgets = tuple(
            WidgetPlacement.from_dict(w) for w in widgets_raw
        )
        # Pre-T134 payloads lack the version field — assume 1.
        version = int(payload.get("version", 1))
        return cls(
            preset_id=str(payload["preset_id"]),
            widgets=widgets,
            version=version,
        )


__all__ = ["ModeOverlayPreset", "WidgetPlacement"]
