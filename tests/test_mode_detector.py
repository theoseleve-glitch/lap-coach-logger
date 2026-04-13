"""Tests for mode_detector -- session type to mode mapping."""
from __future__ import annotations

from lap_coach_logger.core.mode_detector import suggest_mode


class TestSuggestMode:

    def test_practice_suggests_coaching(self) -> None:
        assert suggest_mode("practice") == "coaching"

    def test_qualifying_suggests_coaching(self) -> None:
        assert suggest_mode("qualifying") == "coaching"

    def test_short_race_suggests_sprint(self) -> None:
        assert suggest_mode("race", race_duration_s=1200.0) == "sprint"

    def test_long_race_suggests_endurance(self) -> None:
        assert suggest_mode("race", race_duration_s=3600.0) == "endurance"

    def test_race_without_duration_defaults_sprint(self) -> None:
        assert suggest_mode("race") == "sprint"

    def test_timed_race_suggests_endurance(self) -> None:
        assert suggest_mode("race", is_timed=True) == "endurance"

    def test_time_trial_suggests_coaching(self) -> None:
        assert suggest_mode("time trial") == "coaching"

    def test_unknown_session_suggests_data(self) -> None:
        assert suggest_mode("hotlap") == "data"

    def test_empty_string_suggests_data(self) -> None:
        assert suggest_mode("") == "data"
