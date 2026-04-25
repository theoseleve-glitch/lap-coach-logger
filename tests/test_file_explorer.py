"""T068: ``reveal_in_file_explorer`` is a cross-platform replacement
for the Windows-only ``os.startfile`` calls scattered through
``ui/desktop/service.py``.

Per-platform expectations:

* Windows  -> ``os.startfile(str(path))``
* macOS    -> ``subprocess.run(["open", str(path)])``
* Linux    -> ``subprocess.run(["xdg-open", str(path)])``
* unknown  -> safe no-op (no exception); logs a warning

Tests inject ``platform=`` and ``runner=`` so we never invoke a
real OS file manager. The runner protocol mirrors
``subprocess.run`` (``runner(argv, check=False)``); on Windows the
helper uses ``startfile_fn`` instead because ``startfile`` has no
subprocess equivalent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def existing_dir(tmp_path: Path) -> Path:
    target = tmp_path / "session_2026"
    target.mkdir()
    return target


# ---------------------------------------------------------------------------
# Per-platform dispatch
# ---------------------------------------------------------------------------


def test_windows_uses_os_startfile(existing_dir: Path) -> None:
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    startfile_calls: list[str] = []

    def fake_startfile(path: str) -> None:
        startfile_calls.append(path)

    runner_calls: list[Any] = []
    ok = reveal_in_file_explorer(
        existing_dir,
        platform="win32",
        startfile_fn=fake_startfile,
        runner=lambda *a, **kw: runner_calls.append((a, kw)),
    )

    assert ok is True
    assert startfile_calls == [str(existing_dir)]
    assert runner_calls == [], "Windows must NOT shell out to subprocess"


def test_macos_runs_open_command(existing_dir: Path) -> None:
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    runner_calls: list[Any] = []

    def fake_runner(argv: list[str], **kwargs: object) -> None:
        runner_calls.append((argv, kwargs))

    ok = reveal_in_file_explorer(
        existing_dir,
        platform="darwin",
        runner=fake_runner,
        startfile_fn=lambda _p: pytest.fail("startfile not allowed on macOS"),
    )

    assert ok is True
    assert runner_calls[0][0] == ["open", str(existing_dir)]


def test_linux_runs_xdg_open(existing_dir: Path) -> None:
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    runner_calls: list[Any] = []

    def fake_runner(argv: list[str], **kwargs: object) -> None:
        runner_calls.append((argv, kwargs))

    ok = reveal_in_file_explorer(
        existing_dir,
        platform="linux",
        runner=fake_runner,
        startfile_fn=lambda _p: pytest.fail("startfile not allowed on Linux"),
    )

    assert ok is True
    assert runner_calls[0][0] == ["xdg-open", str(existing_dir)]


@pytest.mark.parametrize("posix_platform", ["linux2", "linux3", "freebsd13"])
def test_linuxlike_platforms_use_xdg_open(
    existing_dir: Path, posix_platform: str
) -> None:
    """``sys.platform`` can be ``linux2``/``freebsd13`` etc.; xdg-open
    is the right answer for every linux-prefixed platform string."""
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    runner_calls: list[Any] = []
    ok = reveal_in_file_explorer(
        existing_dir,
        platform=posix_platform,
        runner=lambda argv, **kw: runner_calls.append(argv),
        startfile_fn=lambda _p: pytest.fail("startfile not allowed"),
    )

    if posix_platform.startswith("linux"):
        assert ok is True
        assert runner_calls[0] == ["xdg-open", str(existing_dir)]
    else:
        # freebsd/other unknown -> safe noop
        assert ok is False
        assert runner_calls == []


def test_unknown_platform_is_a_safe_noop(existing_dir: Path) -> None:
    """A weird platform string (Cygwin, a future port) must not crash."""
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    ok = reveal_in_file_explorer(
        existing_dir,
        platform="haiku",
        runner=lambda *a, **kw: pytest.fail("runner not allowed"),
        startfile_fn=lambda _p: pytest.fail("startfile not allowed"),
    )

    assert ok is False


# ---------------------------------------------------------------------------
# Path validation
# ---------------------------------------------------------------------------


def test_nonexistent_path_returns_false_without_invoking_os(
    tmp_path: Path,
) -> None:
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    runner_calls: list[Any] = []
    startfile_calls: list[str] = []

    ok = reveal_in_file_explorer(
        tmp_path / "nope",
        platform="win32",
        runner=lambda *a, **kw: runner_calls.append((a, kw)),
        startfile_fn=lambda p: startfile_calls.append(p),
    )

    assert ok is False
    assert startfile_calls == []
    assert runner_calls == []


def test_path_is_converted_to_string_for_os_call(existing_dir: Path) -> None:
    """Pure-Path objects must be normalized to str — Windows
    ``os.startfile`` will TypeError on a Path on some Python builds."""
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    startfile_args: list[Any] = []
    reveal_in_file_explorer(
        existing_dir,
        platform="win32",
        startfile_fn=startfile_args.append,
        runner=lambda *a, **kw: None,
    )

    assert isinstance(startfile_args[0], str)


def test_unicode_path_round_trips(tmp_path: Path) -> None:
    """Driver names with unicode (e.g. accented chars) flow into
    output_dir — must not break dispatch."""
    from lap_coach_logger.utils.file_explorer import reveal_in_file_explorer

    target = tmp_path / "Théo's sessions"
    target.mkdir()
    runner_calls: list[Any] = []
    ok = reveal_in_file_explorer(
        target,
        platform="darwin",
        runner=lambda argv, **kw: runner_calls.append(argv),
        startfile_fn=lambda _p: None,
    )

    assert ok is True
    assert runner_calls[0] == ["open", str(target)]


# ---------------------------------------------------------------------------
# Default platform binding (regression guard for production wiring)
# ---------------------------------------------------------------------------


def test_default_platform_uses_sys_platform(
    existing_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``platform`` is not explicitly passed, the helper reads
    ``sys.platform`` so production wiring is a one-arg call."""
    import sys
    from lap_coach_logger.utils import file_explorer

    monkeypatch.setattr(sys, "platform", "darwin")
    runner_calls: list[Any] = []
    ok = file_explorer.reveal_in_file_explorer(
        existing_dir,
        runner=lambda argv, **kw: runner_calls.append(argv),
        startfile_fn=lambda _p: None,
    )

    assert ok is True
    assert runner_calls[0][0] == "open"
