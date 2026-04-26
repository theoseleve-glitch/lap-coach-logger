"""T197: ``scripts/uninstaller_smoke_test.py`` runs the
uninstaller silently and verifies the install dir contains no
orphan files.

T181 declared what gets cleaned (the ``[UninstallDelete]``
+ ``[Registry] uninsdeletevalue`` directives in the .iss);
T197 audits the behavior — runs the uninstaller and reports
any surviving files in the install dir.

Same shape as T196's installer smoke runner: three injection
points (``runner``, ``sleep``, ``list_remaining_files``) keep
the orchestration logic unit-testable offline. Real CI / VM
runs use ``subprocess.run`` / ``time.sleep`` / a real
filesystem walker.

The script returns exit 0 on a clean uninstall (no orphans
detected), 1 on failure — machine-readable for CI consumption.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts" / "uninstaller_smoke_test.py"
)


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location(
        "uninstaller_smoke_test", _SCRIPT_PATH,
    )
    assert spec and spec.loader, (
        f"uninstaller_smoke_test.py must be importable: {_SCRIPT_PATH}"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["uninstaller_smoke_test"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("uninstaller_smoke_test", None)
        raise
    return mod


# -- module exports ---------------------------------------------------


def test_module_exports_public_api(module) -> None:
    """Result type + runner must be exposed."""
    assert hasattr(module, "run_uninstaller_smoke")
    assert hasattr(module, "UninstallResult")


def test_uninstall_result_is_immutable(module) -> None:
    """Frozen dataclass — read-only after construction."""
    from dataclasses import is_dataclass, FrozenInstanceError

    assert is_dataclass(module.UninstallResult)
    r = module.UninstallResult(
        success=True, error=None, orphan_files=[],
    )
    with pytest.raises(FrozenInstanceError):
        r.success = False  # type: ignore[misc]


# -- silent uninstall flags ------------------------------------------


def test_runs_uninstaller_with_silent_flags(
    module, tmp_path: Path,
) -> None:
    """Same flag requirements as T196's installer smoke:
    ``/VERYSILENT`` + ``/SUPPRESSMSGBOXES`` + ``/NORESTART``."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    uninst = install_dir / "unins000.exe"
    uninst.write_bytes(b"fake uninstaller")

    captured = []

    def fake_runner(cmd, **kwargs):
        captured.append(list(cmd))
        # Simulate clean uninstall — remove the install dir.
        for f in install_dir.iterdir():
            f.unlink()
        install_dir.rmdir()

        class R:
            returncode = 0
        return R()

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        uninst, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )

    assert result.success is True
    assert len(captured) == 1
    cmd_str = " ".join(captured[0])
    assert "/VERYSILENT" in cmd_str
    assert "/SUPPRESSMSGBOXES" in cmd_str
    assert "/NORESTART" in cmd_str


# -- happy path: clean uninstall -------------------------------------


def test_clean_uninstall_reports_success(
    module, tmp_path: Path,
) -> None:
    """When the uninstaller exits 0 and the install dir is
    gone (or empty), the smoke must report success with no
    orphans."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    (install_dir / "LapCoachLogger.exe").write_bytes(b"fake app")
    (install_dir / "config.sample.json").write_bytes(b"{}")
    uninst = install_dir / "unins000.exe"
    uninst.write_bytes(b"fake uninstaller")

    def fake_runner(cmd, **kwargs):
        # Simulate Inno's behavior: remove every file in the
        # install dir, then remove the dir.
        for f in install_dir.iterdir():
            f.unlink()
        install_dir.rmdir()

        class R:
            returncode = 0
        return R()

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        uninst, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )

    assert result.success is True
    assert result.orphan_files == []
    assert result.error is None


def test_clean_uninstall_with_empty_remaining_dir_passes(
    module, tmp_path: Path,
) -> None:
    """Inno may leave an empty install dir behind (it cleans
    files, but the dir itself can survive if newer files were
    added at runtime). An empty residual dir is acceptable —
    it's not an orphan file leak."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    uninst = install_dir / "unins000.exe"
    uninst.write_bytes(b"fake uninstaller")

    def fake_runner(cmd, **kwargs):
        # Leave an empty install_dir behind.
        for f in install_dir.iterdir():
            f.unlink()

        class R:
            returncode = 0
        return R()

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        uninst, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )
    assert result.success is True
    assert result.orphan_files == []


# -- failure: orphan files survive -----------------------------------


def test_orphan_files_reported_as_failure(
    module, tmp_path: Path,
) -> None:
    """If files survive in the install dir after uninstall,
    the smoke must report failure with the orphan list — that's
    the bug T197 catches."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    (install_dir / "LapCoachLogger.exe").write_bytes(b"fake")
    (install_dir / "stale_log.txt").write_bytes(b"orphan!")
    uninst = install_dir / "unins000.exe"
    uninst.write_bytes(b"fake uninstaller")

    def fake_runner(cmd, **kwargs):
        # Buggy uninstaller: only removes the .exe and itself,
        # leaving stale_log.txt behind.
        (install_dir / "LapCoachLogger.exe").unlink()
        uninst.unlink()

        class R:
            returncode = 0
        return R()

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        uninst, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )

    assert result.success is False
    assert result.error is not None
    assert "orphan" in result.error.lower()
    # The orphan list must include the surviving file path.
    orphan_names = [Path(p).name for p in result.orphan_files]
    assert "stale_log.txt" in orphan_names


def test_orphan_files_in_subdirs_reported(
    module, tmp_path: Path,
) -> None:
    """Orphans in subdirectories must also be detected — the
    walker must recurse, not just check top-level files."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    sub = install_dir / "qml" / "Onboarding"
    sub.mkdir(parents=True)
    (sub / "OnboardingFlow.qml").write_bytes(b"orphan qml")
    uninst = install_dir / "unins000.exe"
    uninst.write_bytes(b"fake uninstaller")

    def fake_runner(cmd, **kwargs):
        # Buggy: leaves the QML file behind in subdir.
        uninst.unlink()

        class R:
            returncode = 0
        return R()

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        uninst, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )

    assert result.success is False
    orphan_names = [Path(p).name for p in result.orphan_files]
    assert "OnboardingFlow.qml" in orphan_names


# -- error paths -----------------------------------------------------


def test_fails_when_uninstaller_returncode_nonzero(
    module, tmp_path: Path,
) -> None:
    """Uninstaller subprocess exits non-zero → smoke fails
    immediately with the exit code in the error message."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    uninst = install_dir / "unins000.exe"
    uninst.write_bytes(b"fake")

    def fake_runner(cmd, **kwargs):
        class R:
            returncode = 7
        return R()

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        uninst, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )

    assert result.success is False
    assert result.error is not None
    assert "7" in result.error


def test_fails_when_uninstaller_path_missing(
    module, tmp_path: Path,
) -> None:
    """Missing uninstaller path must surface a clear error,
    not a confusing OSError."""
    install_dir = tmp_path / "Install"
    install_dir.mkdir()
    missing = install_dir / "ghost-unins.exe"

    def fake_runner(cmd, **kwargs):
        raise AssertionError("runner must not be called when uninstaller missing")

    def fake_sleep(seconds):
        pass

    result = module.run_uninstaller_smoke(
        missing, install_dir,
        runner=fake_runner,
        sleep=fake_sleep,
    )

    assert result.success is False
    assert result.error is not None
    assert "uninstaller" in result.error.lower()
