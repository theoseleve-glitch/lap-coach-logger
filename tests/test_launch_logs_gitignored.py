"""Regression test: launch_*.log files stay out of git (sprint T019).

The launch wrappers used to dump ``launch_stderr.log`` /
``launch_stdout.log`` into the repo root and the files were once
committed. The sprint task T019 removed them from version control and
requires ``.gitignore`` to keep them out permanently.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GITIGNORE = REPO_ROOT / ".gitignore"
LAUNCH_LOGS = ("launch_stderr.log", "launch_stdout.log")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.splitlines()


def test_launch_logs_not_tracked_by_git() -> None:
    tracked = set(_tracked_files())
    for name in LAUNCH_LOGS:
        assert name not in tracked, (
            f"{name} is still tracked by git — T019 requires removal"
        )


def test_gitignore_covers_log_files() -> None:
    lines = {line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()}
    # Either a broad *.log pattern or explicit per-file entries work.
    broad = "*.log" in lines
    explicit = all(name in lines for name in LAUNCH_LOGS)
    assert broad or explicit, (
        ".gitignore has no pattern covering launch_stderr.log / launch_stdout.log"
    )


def test_launch_logs_would_be_gitignored_if_created() -> None:
    # Ask git directly: if one of these files existed, would it be ignored?
    for name in LAUNCH_LOGS:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "--no-index", name],
            capture_output=True,
            text=True,
        )
        # ``check-ignore`` exits 0 when the path matches a gitignore rule.
        assert result.returncode == 0, (
            f"{name} would NOT be gitignored — .gitignore rule missing"
        )
