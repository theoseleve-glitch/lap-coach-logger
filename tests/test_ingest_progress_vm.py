"""T047: ``IngestProgressViewModel`` reflects SSE events as visible progress.

The view model is the seam between
``infra.sse_progress.SseProgressConsumer`` and the Finalize/Upload
screen — it converts the ADR-012 SSE event vocabulary
(``queued`` / ``processing`` / ``stage:N`` / ``completed`` /
``failed``) into a ``progress_pct`` (0–100) and a human-readable
``stage_label`` that QML/QWidget bindings render directly.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def vm():
    from lap_coach_logger.viewmodels.ingest_progress_vm import (
        IngestProgressViewModel,
    )

    return IngestProgressViewModel()


def test_initial_state_is_zero_and_idle(vm) -> None:
    assert vm.progress_pct == 0
    assert vm.stage_label == "Idle"


def test_queued_event_keeps_progress_at_zero_with_queued_label(vm) -> None:
    vm.on_event({"type": "queued"})
    assert vm.progress_pct == 0
    assert vm.stage_label == "Queued"


def test_processing_event_sets_progress_to_ten(vm) -> None:
    vm.on_event({"type": "processing"})
    assert vm.progress_pct == 10
    assert vm.stage_label == "Processing"


def test_stage_event_advances_progress_proportionally(vm) -> None:
    """``stage:N`` of total 5 stages → 10 + N*16 (rounded)."""
    vm.on_event({"type": "stage:1"})
    assert vm.progress_pct == 26
    vm.on_event({"type": "stage:2"})
    assert vm.progress_pct == 42
    vm.on_event({"type": "stage:5"})
    assert vm.progress_pct == 90


def test_completed_event_sets_progress_to_hundred(vm) -> None:
    vm.on_event({"type": "completed"})
    assert vm.progress_pct == 100
    assert vm.stage_label == "Completed"


def test_failed_event_keeps_progress_and_sets_failed_label(vm) -> None:
    vm.on_event({"type": "stage:2"})
    pct_before = vm.progress_pct
    vm.on_event({"type": "failed"})
    # Progress freezes at last known position; label communicates failure.
    assert vm.progress_pct == pct_before
    assert vm.stage_label == "Failed"


def test_progress_changed_signal_fires_per_event(vm) -> None:
    seen: list[tuple[int, str]] = []
    vm.progress_changed.connect(lambda pct, label: seen.append((pct, label)))

    vm.on_event({"type": "queued"})
    vm.on_event({"type": "processing"})
    vm.on_event({"type": "completed"})

    assert seen == [(0, "Queued"), (10, "Processing"), (100, "Completed")]


def test_progress_changed_does_not_fire_when_unchanged(vm) -> None:
    """Two identical events in a row must not double-emit."""
    seen: list[tuple[int, str]] = []
    vm.progress_changed.connect(lambda pct, label: seen.append((pct, label)))

    vm.on_event({"type": "processing"})
    vm.on_event({"type": "processing"})

    assert seen == [(10, "Processing")]


def test_unknown_event_type_is_ignored(vm) -> None:
    vm.on_event({"type": "unrelated_chatter"})
    assert vm.progress_pct == 0
    assert vm.stage_label == "Idle"


def test_event_with_explicit_progress_pct_is_honoured(vm) -> None:
    """The backend can pass ``progress_pct`` explicitly to override the default."""
    vm.on_event({"type": "processing", "progress_pct": 47})
    assert vm.progress_pct == 47


def test_view_model_subscribes_to_sse_consumer_event_received() -> None:
    """A helper wires ``vm.on_event`` to ``consumer.event_received`` cleanly."""
    from lap_coach_logger.infra.sse_progress import SseProgressConsumer
    from lap_coach_logger.viewmodels.ingest_progress_vm import (
        IngestProgressViewModel,
        bind_to_consumer,
    )

    consumer = SseProgressConsumer(
        base_url="http://unused.test", job_id="j", auth_token="t"
    )
    vm = IngestProgressViewModel()
    bind_to_consumer(vm, consumer)

    # Direct emit (no real HTTP) must reach the VM.
    consumer.event_received.emit({"type": "completed"})
    assert vm.progress_pct == 100
    assert vm.stage_label == "Completed"
