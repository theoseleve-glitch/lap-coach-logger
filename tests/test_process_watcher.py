from __future__ import annotations

from unittest.mock import Mock, patch

from lap_coach_logger.detection.process_watcher import ProcessWatcher


class _Adapter:
    def __init__(self, sim_name: str, *process_names: str) -> None:
        self.sim_name = sim_name
        self.process_names = list(process_names)


def test_process_watcher_does_not_latch_adapter_when_callback_rejects() -> None:
    adapter = _Adapter("iRacing", "iRacingSim64DX11.exe")
    on_found = Mock(return_value=False)
    watcher = ProcessWatcher([adapter], on_sim_found=on_found)

    with patch.object(ProcessWatcher, "_snapshot_process_names", return_value={"iracingsim64dx11.exe"}):
        watcher._poll_once()

    on_found.assert_called_once_with(adapter, True)
    assert watcher.active_adapter is None


def test_process_watcher_retries_until_callback_accepts() -> None:
    adapter = _Adapter("iRacing", "iRacingSim64DX11.exe")
    on_found = Mock(side_effect=[False, True])
    watcher = ProcessWatcher([adapter], on_sim_found=on_found)

    with patch.object(ProcessWatcher, "_snapshot_process_names", return_value={"iracingsim64dx11.exe"}):
        watcher._poll_once()
        watcher._poll_once()

    assert on_found.call_count == 2
    assert watcher.active_adapter is adapter