import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

# Skip if no display available (CI environments)
pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY") is None and sys.platform != "win32",
    reason="No display available"
)


def test_ghost_overlay_instantiation():
    """GhostCoachOverlay can be created and updated without crash."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from lap_coach_logger.ui.desktop.ghost_overlay import GhostCoachOverlay
        widget = GhostCoachOverlay()
        assert widget is not None

        # Update with empty snapshot (no ghost loaded)
        widget.update_from_snapshot({})

        # Update with full snapshot
        widget.update_from_snapshot({
            "ghost_speed_delta_kph": 12.5,
            "ghost_throttle_delta_pct": 0.15,
            "ghost_brake_delta_pct": -0.05,
            "ghost_steering_delta_deg": 3.2,
            "ghost_cumulative_delta_s": 0.342,
            "ghost_theoretical_speed_kph": 195.0,
            "ghost_theoretical_throttle_pct": 0.92,
            "ghost_theoretical_brake_pct": 0.0,
            "ghost_theoretical_steering_deg": -42.0,
            "ghost_loaded": True,
        })

        # Update with negative delta (driver ahead)
        widget.update_from_snapshot({
            "ghost_speed_delta_kph": -5.0,
            "ghost_cumulative_delta_s": -0.150,
            "ghost_theoretical_speed_kph": 180.0,
            "ghost_theoretical_throttle_pct": 0.5,
            "ghost_theoretical_brake_pct": 0.3,
            "ghost_theoretical_steering_deg": 10.0,
            "ghost_throttle_delta_pct": 0.0,
            "ghost_brake_delta_pct": 0.0,
            "ghost_steering_delta_deg": 0.0,
            "ghost_loaded": True,
        })
    except ImportError:
        pytest.skip("PySide6 not available")


def test_ghost_bar_widget():
    """GhostBarWidget renders without crash."""
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from lap_coach_logger.ui.desktop.ghost_overlay import GhostBarWidget
        bar = GhostBarWidget("#22C55E")
        bar.set_values(0.7, 0.9)
        assert bar._actual == pytest.approx(0.7)
        assert bar._ghost == pytest.approx(0.9)
    except ImportError:
        pytest.skip("PySide6 not available")
