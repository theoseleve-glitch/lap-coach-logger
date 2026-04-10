"""Tests for strategy_weather module — iRacing weather forecast parsing."""

from lap_coach_logger.core.strategy_weather import (
    ConditionWindow,
    parse_forecast,
    update_from_live,
)


class TestParseDryForecast:
    """All windows should be classified as dry with soft compound."""

    def test_single_dry_entry(self):
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 28.0, "precipitation": 0.0},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=20)

        assert len(windows) == 1
        assert windows[0].track_state == "dry"
        assert windows[0].recommended_compound == "soft"
        assert windows[0].start_lap == 1
        assert windows[0].end_lap == 20

    def test_multiple_dry_entries(self):
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 25.0, "precipitation": 0.05},
                    {"time": 900.0, "temperature": 27.0, "precipitation": 0.10},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=20)

        assert len(windows) == 2
        for w in windows:
            assert w.track_state == "dry"
            assert w.recommended_compound == "soft"

    def test_dry_boundary_at_threshold(self):
        """precipitation = 0.14 (just below 0.15) is still dry."""
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 30.0, "precipitation": 0.14},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=80.0, total_laps=10)

        assert len(windows) == 1
        assert windows[0].track_state == "dry"


class TestParseRainForecast:
    """Mix of dry and wet windows with correct compound recommendations."""

    def test_dry_to_wet_transition(self):
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 26.0, "precipitation": 0.05},
                    {"time": 900.0, "temperature": 22.0, "precipitation": 0.6},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=20)

        assert len(windows) == 2
        # First window: dry
        assert windows[0].track_state == "dry"
        assert windows[0].recommended_compound == "soft"
        # Second window: wet
        assert windows[1].track_state == "wet"
        assert windows[1].recommended_compound == "wet"

    def test_damp_classification(self):
        """precipitation between 0.15 and 0.4 → damp / inter."""
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 24.0, "precipitation": 0.25},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=15)

        assert len(windows) == 1
        assert windows[0].track_state == "damp"
        assert windows[0].recommended_compound == "inter"

    def test_three_phase_weather(self):
        """dry → damp → wet across three segments."""
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 30.0, "precipitation": 0.0},
                    {"time": 600.0, "temperature": 25.0, "precipitation": 0.3},
                    {"time": 1200.0, "temperature": 20.0, "precipitation": 0.8},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=100.0, total_laps=20)

        assert len(windows) == 3
        assert windows[0].track_state == "dry"
        assert windows[1].track_state == "damp"
        assert windows[2].track_state == "wet"
        assert windows[0].recommended_compound == "soft"
        assert windows[1].recommended_compound == "inter"
        assert windows[2].recommended_compound == "wet"

    def test_temperature_preserved(self):
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 35.5, "precipitation": 0.5},
                ],
            },
        }
        windows = parse_forecast(session_info, lap_time_s=90.0, total_laps=10)

        assert windows[0].track_temp_c == 35.5


class TestParseEmptyForecast:
    """Returns [] when forecast data is empty or missing."""

    def test_empty_forecast_list(self):
        session_info = {"WeatherInfo": {"WeatherForecast": []}}
        assert parse_forecast(session_info, lap_time_s=90.0, total_laps=20) == []

    def test_missing_weather_info_key(self):
        assert parse_forecast({}, lap_time_s=90.0, total_laps=20) == []

    def test_missing_forecast_key(self):
        session_info = {"WeatherInfo": {}}
        assert parse_forecast(session_info, lap_time_s=90.0, total_laps=20) == []

    def test_none_session_info(self):
        assert parse_forecast(None, lap_time_s=90.0, total_laps=20) == []

    def test_zero_lap_time(self):
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 25.0, "precipitation": 0.0},
                ],
            },
        }
        assert parse_forecast(session_info, lap_time_s=0.0, total_laps=20) == []

    def test_zero_total_laps(self):
        session_info = {
            "WeatherInfo": {
                "WeatherForecast": [
                    {"time": 0.0, "temperature": 25.0, "precipitation": 0.0},
                ],
            },
        }
        assert parse_forecast(session_info, lap_time_s=90.0, total_laps=0) == []


class TestUpdateFromLive:
    """Adjusts the current window with actual conditions."""

    def test_adjusts_current_window(self):
        windows = [
            ConditionWindow(
                start_lap=1, end_lap=10,
                track_temp_c=28.0, precipitation=0.05,
                track_state="dry", recommended_compound="soft",
            ),
            ConditionWindow(
                start_lap=11, end_lap=20,
                track_temp_c=22.0, precipitation=0.6,
                track_state="wet", recommended_compound="wet",
            ),
        ]

        updated = update_from_live(
            current_windows=windows,
            precipitation=0.35,
            track_wetness=0.5,
            track_temp=24.0,
            current_lap=5,
        )

        # Current window (lap 5 → window 1) updated with actual data
        assert updated[0].track_temp_c == 24.0
        assert updated[0].precipitation == 0.35
        assert updated[0].track_state == "damp"
        assert updated[0].recommended_compound == "inter"

        # Future window unchanged
        assert updated[1].track_temp_c == 22.0
        assert updated[1].precipitation == 0.6
        assert updated[1].track_state == "wet"
        assert updated[1].recommended_compound == "wet"

    def test_empty_windows_returns_empty(self):
        assert update_from_live([], 0.5, 0.5, 25.0, 5) == []

    def test_past_window_not_modified(self):
        windows = [
            ConditionWindow(
                start_lap=1, end_lap=5,
                track_temp_c=30.0, precipitation=0.0,
                track_state="dry", recommended_compound="soft",
            ),
            ConditionWindow(
                start_lap=6, end_lap=15,
                track_temp_c=25.0, precipitation=0.5,
                track_state="wet", recommended_compound="wet",
            ),
        ]

        updated = update_from_live(
            current_windows=windows,
            precipitation=0.7,
            track_wetness=0.8,
            track_temp=20.0,
            current_lap=10,
        )

        # Past window (laps 1-5) stays original
        assert updated[0].track_temp_c == 30.0
        assert updated[0].track_state == "dry"

        # Current window (laps 6-15) updated
        assert updated[1].track_temp_c == 20.0
        assert updated[1].precipitation == 0.7
        assert updated[1].track_state == "wet"
