"""T196: ``scripts/installer_smoke_test.py`` runs a silent
install + launch + verify on a clean Windows runner.

The deliverable is a script that can be invoked from CI (after
the build step on a clean ``windows-2019`` / ``windows-2022``
runner) or manually by a release manager. The script:

1. Runs the installer ``.exe`` with ``/VERYSILENT`` +
   ``/SUPPRESSMSGBOXES`` for unattended CI execution.
2. Launches the installed application binary.
3. Waits a grace period (default 10 s) for startup.
4. Verifies the process is still running (alive after grace
   = clean launch; exit-during-init = failure).
5. Returns a :class:`SmokeResult` with success/error.

Three injection points (``runner``, ``process_starter``,
``sleep``) keep the orchestration logic unit-testable offline.
The CLI wrapper uses real ``subprocess`` + ``time.sleep``.

T196's "⇒ runs" criterion: the smoke runs (the script exists
and is wired). Actual execution happens when a release tag is
pushed and the CI build job calls this script.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts" / "installer_smoke_test.py"
)


@pytest.fixture(scope="module")
def module():
    """Load the script as a module (it's not in src/ so not
    importable as a package)."""
    spec = importlib.util.spec_from_file_location(
        "installer_smoke_test", _SCRIPT_PATH,
    )
    assert spec and spec.loader, (
        f"installer_smoke_test.py must be importable: {_SCRIPT_PATH}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["installer_smoke_test"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("installer_smoke_test", None)
        raise
    return mod


# -- module exports ---------------------------------------------------


def test_module_exports_public_api(module) -> None:
    """The smoke runner + result type must be exposed."""
    assert hasattr(module, "run_installer_smoke")
    assert hasattr(module, "SmokeResult")


def test_smoke_result_is_immutable(module) -> None:
    """Frozen dataclass — orchestration result is read-only."""
    from dataclasses import is_dataclass, FrozenInstanceError

    assert is_dataclass(module.SmokeResult)
    r = module.SmokeResult(success=True, error=None, launched_pid=1234)
    with pytest.raises(FrozenInstanceError):
        r.success = False  # type: ignore[misc]


# -- silent install flags --------------------------------------------


def test_runs_installer_with_silent_flags(
    module, tmp_path: Path,
) -> None:
    """The installer subprocess must be invoked with
    ``/VERYSILENT`` *and* ``/SUPPRESSMSGBOXES`` — without
    both flags the CI job stalls on installer dialogs."""
    installer = tmp_path / "LapCoachLogger-Setup.exe"
    installer.write_bytes(b"fake installer")
    install_dir = tmp_path / "Install"
    app_exe = install_dir / "LapCoachLogger.exe"

    captured_runner_calls = []

    def fake_runner(cmd, **kwargs):
        captured_runner_calls.append({
            "cmd": list(cmd),
            "kwargs": dict(kwargs),
        })
        # Simulate the installer "creating" the app exe so
        # subsequent steps can see it.
        install_dir.mkdir(parents=True, exist_ok=True)
        app_exe.write_bytes(b"fake app")

        class Result:
            returncode = 0
        return Result()

    class FakeProc:
        def __init__(self):
            self.pid = 9999
        def poll(self):
            return None  # still running
        def terminate(self):
            pass
        def wait(self, timeout=None):
            return 0

    def fake_starter(cmd, **kwargs):
        return FakeProc()

    def fake_sleep(seconds):
        pass

    result = module.run_installer_smoke(
        installer, install_dir, app_exe,
        runner=fake_runner,
        process_starter=fake_starter,
        sleep=fake_sleep,
    )

    assert result.success is True
    assert len(captured_runner_calls) >= 1
    install_cmd = captured_runner_calls[0]["cmd"]
    install_cmd_str = " ".join(install_cmd)
    assert "/VERYSILENT" in install_cmd_str, (
        f"installer must be invoked with /VERYSILENT for "
        f"unattended CI; got cmd: {install_cmd_str}"
    )
    assert "/SUPPRESSMSGBOXES" in install_cmd_str, (
        f"installer must be invoked with /SUPPRESSMSGBOXES "
        f"so error popups don't stall the CI job; got cmd: "
        f"{install_cmd_str}"
    )


# -- launches app + checks alive --------------------------------------


def test_launches_installed_app_and_verifies_alive(
    module, tmp_path: Path,
) -> None:
    """After a successful install, the script must launch
    the app exe and verify it survives the grace period."""
    installer = tmp_path / "LapCoachLogger-Setup.exe"
    installer.write_bytes(b"fake")
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    app_exe = install_dir / "LapCoachLogger.exe"
    app_exe.write_bytes(b"fake app")

    starter_called_with = []

    def fake_runner(cmd, **kwargs):
        class R:
            returncode = 0
        return R()

    class FakeProc:
        def __init__(self):
            self.pid = 4321
        def poll(self):
            return None  # alive
        def terminate(self):
            pass
        def wait(self, timeout=None):
            return 0

    def fake_starter(cmd, **kwargs):
        starter_called_with.append(list(cmd))
        return FakeProc()

    def fake_sleep(seconds):
        pass

    result = module.run_installer_smoke(
        installer, install_dir, app_exe,
        runner=fake_runner,
        process_starter=fake_starter,
        sleep=fake_sleep,
    )

    assert result.success is True
    assert result.launched_pid == 4321
    assert len(starter_called_with) == 1
    assert str(app_exe) in starter_called_with[0][0] or (
        str(app_exe) in " ".join(starter_called_with[0])
    )


def test_fails_when_app_exits_during_grace_period(
    module, tmp_path: Path,
) -> None:
    """If the launched process exits during the grace period
    (init crash, DLL missing, bad config), the smoke must
    return ``success=False`` with a captured error."""
    installer = tmp_path / "LapCoachLogger-Setup.exe"
    installer.write_bytes(b"fake")
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    app_exe = install_dir / "LapCoachLogger.exe"
    app_exe.write_bytes(b"fake")

    def fake_runner(cmd, **kwargs):
        class R:
            returncode = 0
        return R()

    class CrashingProc:
        def __init__(self):
            self.pid = 1111
        def poll(self):
            return 1  # exited with code 1 — crashed
        def terminate(self):
            pass
        def wait(self, timeout=None):
            return 1

    def fake_starter(cmd, **kwargs):
        return CrashingProc()

    def fake_sleep(seconds):
        pass

    result = module.run_installer_smoke(
        installer, install_dir, app_exe,
        runner=fake_runner,
        process_starter=fake_starter,
        sleep=fake_sleep,
    )

    assert result.success is False
    assert result.error is not None
    assert "exit" in result.error.lower() or "crash" in result.error.lower()


# -- error paths ------------------------------------------------------


def test_fails_when_installer_returncode_nonzero(
    module, tmp_path: Path,
) -> None:
    """Installer subprocess exits non-zero → smoke fails
    immediately (no point launching an app that didn't
    install)."""
    installer = tmp_path / "LapCoachLogger-Setup.exe"
    installer.write_bytes(b"fake")
    install_dir = tmp_path / "Install"
    app_exe = install_dir / "LapCoachLogger.exe"

    def fake_runner(cmd, **kwargs):
        class R:
            returncode = 5  # installer reported failure
        return R()

    starter_called = []

    def fake_starter(cmd, **kwargs):
        starter_called.append(cmd)
        raise AssertionError("starter must not be called when install fails")

    def fake_sleep(seconds):
        pass

    result = module.run_installer_smoke(
        installer, install_dir, app_exe,
        runner=fake_runner,
        process_starter=fake_starter,
        sleep=fake_sleep,
    )

    assert result.success is False
    assert result.error is not None
    assert "5" in result.error or "install" in result.error.lower()
    assert starter_called == [], (
        "process_starter must not be called when the installer "
        "subprocess failed"
    )


def test_fails_when_installer_path_missing(
    module, tmp_path: Path,
) -> None:
    """Pointing at a non-existent installer must fail with a
    clear error, not a confusing OSError."""
    missing = tmp_path / "does-not-exist.exe"
    install_dir = tmp_path / "Install"
    app_exe = install_dir / "LapCoachLogger.exe"

    def fake_runner(cmd, **kwargs):
        raise AssertionError("runner must not be called when installer missing")

    def fake_starter(cmd, **kwargs):
        raise AssertionError("starter must not be called")

    def fake_sleep(seconds):
        pass

    result = module.run_installer_smoke(
        missing, install_dir, app_exe,
        runner=fake_runner,
        process_starter=fake_starter,
        sleep=fake_sleep,
    )

    assert result.success is False
    assert result.error is not None
    assert "installer" in result.error.lower()


def test_terminates_app_on_success_for_clean_runner(
    module, tmp_path: Path,
) -> None:
    """After a successful smoke the launched app must be
    terminated — otherwise CI runners pile up zombie processes
    across runs."""
    installer = tmp_path / "LapCoachLogger-Setup.exe"
    installer.write_bytes(b"fake")
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    app_exe = install_dir / "LapCoachLogger.exe"
    app_exe.write_bytes(b"fake")

    def fake_runner(cmd, **kwargs):
        class R:
            returncode = 0
        return R()

    terminate_called = [False]

    class FakeProc:
        def __init__(self):
            self.pid = 7777
        def poll(self):
            return None  # alive
        def terminate(self):
            terminate_called[0] = True
        def wait(self, timeout=None):
            return 0

    def fake_starter(cmd, **kwargs):
        return FakeProc()

    def fake_sleep(seconds):
        pass

    result = module.run_installer_smoke(
        installer, install_dir, app_exe,
        runner=fake_runner,
        process_starter=fake_starter,
        sleep=fake_sleep,
    )

    assert result.success is True
    assert terminate_called[0] is True, (
        "successful smoke must terminate the launched process "
        "so CI runners don't accumulate zombies"
    )
