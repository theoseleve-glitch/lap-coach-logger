"""Tests for demo playback runner."""
from __future__ import annotations

from lap_coach_logger.demo.runner import DemoPhase, DemoRunner


class TestLifecycle:

    def test_start_builds_session(self):
        snaps = []
        runner = DemoRunner(snapshot_sink=snaps.append)
        runner.start()
        assert runner.session is not None
        assert runner.state.active is True
        assert runner.state.current_lap == 0

    def test_stop_resets_state(self):
        runner = DemoRunner(snapshot_sink=lambda s: None)
        runner.start()
        runner.stop()
        assert runner.state.active is False
        assert runner.session is None


class TestStepping:

    def test_step_lap_advances(self):
        snaps = []
        runner = DemoRunner(snapshot_sink=snaps.append)
        runner.start()
        assert runner.step_lap() is True
        assert runner.state.current_lap == 1
        # All snapshots for lap 1 were pushed
        assert len(snaps) == runner.session.samples_per_lap

    def test_step_lap_returns_false_at_end(self):
        runner = DemoRunner(snapshot_sink=lambda s: None)
        runner.start()
        for _ in range(runner.session.total_laps):
            runner.step_lap()
        assert runner.step_lap() is False
        assert runner.state.phase == DemoPhase.DONE

    def test_step_sample_advances_within_lap(self):
        snaps = []
        runner = DemoRunner(snapshot_sink=snaps.append)
        runner.start()
        runner.step_sample()
        assert len(snaps) == 1
        assert runner.state.current_sample_in_lap == 1


class TestPhaseTransitions:

    def test_phase_advances_at_lap_6(self):
        phases = []
        runner = DemoRunner(
            snapshot_sink=lambda s: None,
            phase_sink=phases.append,
        )
        runner.start()
        for _ in range(6):
            runner.step_lap()
        # Phases emitted: INTRO, COACHING, SPRINT
        assert DemoPhase.SPRINT in phases

    def test_jump_to_endurance(self):
        runner = DemoRunner(snapshot_sink=lambda s: None)
        runner.start()
        runner.jump_to_phase(DemoPhase.ENDURANCE)
        assert runner.state.current_lap >= 8


class TestMomentSink:

    def test_moments_fire_at_scripted_laps(self):
        moments = []
        runner = DemoRunner(
            snapshot_sink=lambda s: None,
            moment_sink=moments.append,
        )
        runner.start()
        for _ in range(10):
            runner.step_lap()
        assert len(moments) >= 4
        assert any("plan" in m.title.lower() for m in moments)


class TestReset:

    def test_reset_returns_to_lap_zero(self):
        runner = DemoRunner(snapshot_sink=lambda s: None)
        runner.start()
        runner.step_lap()
        runner.step_lap()
        assert runner.state.current_lap == 2
        runner.reset()
        assert runner.state.current_lap == 0
        assert runner.state.active is True


class TestDeterminism:

    def test_same_inputs_produce_same_outputs(self):
        snaps1 = []
        runner1 = DemoRunner(snapshot_sink=snaps1.append)
        runner1.start()
        runner1.play_to_completion()

        snaps2 = []
        runner2 = DemoRunner(snapshot_sink=snaps2.append)
        runner2.start()
        runner2.play_to_completion()

        assert len(snaps1) == len(snaps2)
        for s1, s2 in zip(snaps1, snaps2):
            assert s1["lap_number"] == s2["lap_number"]
            assert s1["fuel_level"] == s2["fuel_level"]
