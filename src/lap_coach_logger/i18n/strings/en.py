"""English source-of-truth catalog.

Every key referenced from the codebase MUST appear here. Other
locales fall back to English when their key is missing, so adding
a new string = add it here first, then translators stub in
``fr.py`` (and future locales) at their own pace.
"""
from __future__ import annotations

STRINGS: dict[str, str] = {
    # Built-in overlays — display name + short description shown in
    # the overlay picker. Keys mirror ``overlays/builtins.py``.
    "overlay.radar_awareness.name": "Radar Awareness",
    "overlay.radar_awareness.description": (
        "Spatial awareness of nearby cars with closure-rate cues."
    ),
    "overlay.spotter_awareness.name": "Spotter Awareness",
    "overlay.spotter_awareness.description": (
        "Side-by-side and overlap callouts for race traffic."
    ),
    "overlay.session_delta.name": "Session Delta",
    "overlay.session_delta.description": (
        "Live delta vs. your best lap of the session."
    ),
    "overlay.theoretical_ghost.name": "Theoretical Ghost",
    "overlay.theoretical_ghost.description": (
        "Delta vs. an optimal lap stitched from your best sectors."
    ),
    "overlay.sector_table.name": "Sector Table",
    "overlay.sector_table.description": (
        "Per-sector breakdown with personal-best highlighting."
    ),
}
