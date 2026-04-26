"""T195: CI build job runs across a Windows 10 + 11 matrix.

GitHub Actions' Windows runners use Server SKUs as proxies for
desktop versions:

- ``windows-2019`` — Windows Server 2019, the Win10-class
  runner (same kernel, same WinAPI surface).
- ``windows-2022`` — Windows Server 2022, the Win11-class
  runner.
- ``windows-latest`` floats (currently 2022).

Pinning *explicit* version labels guarantees that when GitHub
flips ``windows-latest`` forward to a future SKU, both real
targets (Win10 + Win11) stay covered.

T195 pins:

1. The CI workflow exists at ``.github/workflows/ci.yml``.
2. The build job has a ``strategy.matrix`` declaration.
3. The matrix references both ``windows-2019`` and
   ``windows-2022``.
4. ``fail-fast: false`` so one OS failing doesn't cancel the
   other (otherwise we lose coverage on every flaky run).
5. Artifact names include the matrix OS so each matrix job
   uploads to a distinct name (otherwise the second upload
   fails on duplicate-name conflict).

Source-content pin (consistent with T175-T194).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_CI_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github" / "workflows" / "ci.yml"
)


@pytest.fixture(scope="module")
def ci_text() -> str:
    return _CI_PATH.read_text(encoding="utf-8")


def _build_job_block(ci_text: str) -> str:
    """Slice the build: job from `build:` to the next top-level
    `<key>:` (a key sitting at column-2 indent, since we're
    inside `jobs:` at column 0)."""
    # The 'jobs:' block lives at top level; each job is
    # indented 2 spaces. Match `  build:` and capture until
    # the next `  <something>:` or EOF.
    match = re.search(
        r'^\s{2}build\s*:\n([\s\S]*?)(?=^\s{2}\w[\w-]*\s*:|\Z)',
        ci_text,
        re.MULTILINE,
    )
    assert match is not None, (
        "ci.yml must have a `build:` job under `jobs:`"
    )
    return match.group(1)


# -- workflow file present --------------------------------------------


def test_ci_workflow_file_exists() -> None:
    """The CI workflow file is the entry point — without it
    the rest of T195 is moot."""
    assert _CI_PATH.is_file(), (
        f".github/workflows/ci.yml must exist at {_CI_PATH}"
    )


# -- build job has a matrix ------------------------------------------


def test_build_job_declares_strategy_matrix(ci_text: str) -> None:
    """The build job must declare a strategy/matrix so it runs
    multiple OS targets per push."""
    block = _build_job_block(ci_text)
    assert re.search(
        r'^\s+strategy\s*:',
        block,
        re.MULTILINE,
    ), "build job must declare a `strategy:` section for the matrix"
    assert re.search(
        r'^\s+matrix\s*:',
        block,
        re.MULTILINE,
    ), "build job's strategy must include a `matrix:` declaration"


# -- both Windows runners pinned -------------------------------------


@pytest.mark.parametrize(
    "runner,role",
    [
        ("windows-2019", "Win10-class"),
        ("windows-2022", "Win11-class"),
    ],
)
def test_build_matrix_includes_runner(
    ci_text: str, runner: str, role: str,
) -> None:
    """Each Windows desktop version must have a matching
    runner in the matrix. Without explicit version pinning,
    `windows-latest` floats and we silently lose coverage of
    one of the targets."""
    block = _build_job_block(ci_text)
    assert runner in block, (
        f"build matrix must include `{runner}` ({role}); "
        f"otherwise T195's promise to test both Win10 + Win11 "
        f"is not kept"
    )


# -- runs-on uses matrix variable ------------------------------------


def test_build_runs_on_uses_matrix_os(ci_text: str) -> None:
    """``runs-on`` must reference the matrix variable so each
    job actually runs on the matching OS — otherwise the
    matrix is decorative and all jobs run on the same fixed
    runner."""
    block = _build_job_block(ci_text)
    assert re.search(
        r'^\s+runs-on\s*:\s*\$\{\{\s*matrix\.\w+\s*\}\}',
        block,
        re.MULTILINE,
    ), (
        "build job's `runs-on:` must reference a matrix "
        "variable like `${{ matrix.os }}` so each matrix job "
        "actually targets a different OS"
    )


# -- fail-fast: false -------------------------------------------------


def test_build_matrix_does_not_fail_fast(ci_text: str) -> None:
    """``fail-fast: false`` is required — with the default
    (true), a failure on one OS cancels the other matrix jobs
    mid-run, hiding coverage. We want each OS to complete
    independently."""
    block = _build_job_block(ci_text)
    assert re.search(
        r'^\s+fail-fast\s*:\s*false',
        block,
        re.MULTILINE,
    ), (
        "build matrix must declare `fail-fast: false` so a "
        "failure on one OS doesn't cancel the other matrix jobs"
    )


# -- artifact names disambiguate per OS ------------------------------


def test_artifact_name_includes_matrix_os(ci_text: str) -> None:
    """When the matrix has 2+ jobs, each must upload to a
    distinct artifact name. Otherwise the second matrix job's
    upload fails on duplicate-name conflict, killing the
    build."""
    block = _build_job_block(ci_text)
    # Find the artifact upload step.
    upload_match = re.search(
        r'upload-artifact[\s\S]+?(?=^\s{6}-\s|\Z)',
        block,
        re.MULTILINE,
    )
    assert upload_match is not None, (
        "build job must have an `upload-artifact` step"
    )
    upload_block = upload_match.group(0)
    # The name field must reference matrix.os (or matrix.<key>)
    # so each matrix job uploads to a distinct name.
    assert re.search(
        r'name\s*:[^\n]*\$\{\{\s*matrix\.\w+\s*\}\}',
        upload_block,
    ), (
        "artifact upload `name:` must include a matrix "
        "variable (e.g. `${{ matrix.os }}`) so each matrix "
        "job uploads to a distinct artifact name"
    )
