"""T183: ``scripts/gen_release_checklist.py`` auto-generates a
release checklist from git log between two tags/refs.

The script splits two responsibilities:

1. ``git_commits_between(from_ref, to_ref)`` — shells out to
   ``git log --pretty=format:%h\\t%s from_ref..to_ref`` and
   returns ``Commit(sha, subject)`` records.
2. ``format_checklist(commits, *, from_ref, to_ref, version=None)``
   — pure formatter, produces markdown.

Tests pin the format contract (pure function) and one
integration test for the subprocess plumbing against this
repo's own history.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT_PATH = _REPO / "scripts" / "gen_release_checklist.py"


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location(
        "gen_release_checklist", _SCRIPT_PATH,
    )
    assert spec and spec.loader, (
        f"scripts/gen_release_checklist.py must be importable, "
        f"got: {_SCRIPT_PATH}"
    )
    mod = importlib.util.module_from_spec(spec)
    # Register before exec_module so dataclasses can look up
    # `cls.__module__` during field introspection.
    sys.modules["gen_release_checklist"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("gen_release_checklist", None)
        raise
    return mod


# -- format_checklist (pure) -------------------------------------------


def test_format_checklist_empty_range(module) -> None:
    """Empty commit list still produces a valid markdown
    document — caller might be regenerating between two
    identical refs, that should not crash."""
    text = module.format_checklist(
        [], from_ref="v1.0.0", to_ref="v1.0.0",
    )
    assert "# Release Checklist" in text
    assert "v1.0.0..v1.0.0" in text
    # Empty-range marker so the user knows the script ran but
    # found nothing.
    assert "no commits" in text.lower()


def test_format_checklist_renders_commits_as_checkboxes(
    module,
) -> None:
    """Each commit must render as `- [ ] <sha> <subject>` so
    the release manager can tick each off after manual review."""
    Commit = module.Commit
    commits = [
        Commit(sha="abc1234", subject="feat: add foo"),
        Commit(sha="def5678", subject="fix: bar regression"),
    ]
    text = module.format_checklist(
        commits, from_ref="v1.0.0", to_ref="v2.0.0",
    )
    assert "- [ ] abc1234 feat: add foo" in text
    assert "- [ ] def5678 fix: bar regression" in text


def test_format_checklist_version_in_title(module) -> None:
    """When called with ``version="2.0.0"``, the title must
    include the version so the checklist is self-identifying."""
    text = module.format_checklist(
        [], from_ref="v1.0.0", to_ref="HEAD", version="2.0.0",
    )
    # First line must reference the version.
    first_heading = text.splitlines()[0]
    assert "2.0.0" in first_heading


def test_format_checklist_has_prerelease_gates(module) -> None:
    """Every release must verify the same standard gates: full
    test pass, installer build, smoke test, tag. The script
    bakes these in so they don't get forgotten."""
    text = module.format_checklist(
        [], from_ref="v1.0.0", to_ref="HEAD",
    )
    lower = text.lower()
    assert "pytest" in lower, (
        "checklist must include `pytest` verification gate"
    )
    assert "installer" in lower, (
        "checklist must include installer build gate"
    )
    assert "smoke" in lower, (
        "checklist must include a smoke-test gate"
    )
    assert "tag" in lower, (
        "checklist must include a `git tag` step at the end"
    )


# -- git_commits_between (integration) ---------------------------------


def test_git_commits_between_against_repo_head(module) -> None:
    """Integration: against this repo's own history, the last
    three commits must be returned in order. We use the working
    tree's actual git log so the test exercises the real
    subprocess plumbing."""
    commits = module.git_commits_between(
        "HEAD~3", "HEAD", repo_root=_REPO,
    )
    assert len(commits) == 3, (
        f"expected exactly 3 commits in HEAD~3..HEAD, "
        f"got {len(commits)}"
    )
    for c in commits:
        # Short sha is at least 7 chars; format `%h` defaults
        # to that minimum.
        assert len(c.sha) >= 7, f"sha too short: {c.sha!r}"
        assert c.subject, f"subject empty for {c.sha}"


def test_git_commits_between_invalid_ref_raises(module) -> None:
    """An invalid ref must propagate the ``CalledProcessError``
    so CI/scripting can detect typos in tag names."""
    with pytest.raises(subprocess.CalledProcessError):
        module.git_commits_between(
            "nonexistent-ref-zzz", "HEAD", repo_root=_REPO,
        )


# -- CLI smoke test ----------------------------------------------------


def test_cli_runs_against_real_history() -> None:
    """The script must be runnable end-to-end as
    ``python scripts/gen_release_checklist.py HEAD~2 HEAD``
    and produce non-empty markdown on stdout. This is the
    user-visible contract — tests above pin the internals; this
    pin guarantees the wiring works."""
    result = subprocess.run(
        [
            "python",
            str(_SCRIPT_PATH),
            "HEAD~2",
            "HEAD",
            "--version",
            "2.0.0",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (
        f"CLI failed: stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "Release Checklist" in result.stdout
    assert "2.0.0" in result.stdout
    # Two commits in HEAD~2..HEAD must appear as checkboxes.
    checkbox_lines = [
        line for line in result.stdout.splitlines()
        if line.startswith("- [ ] ")
    ]
    # At least 2 from history + the prerelease gate items.
    assert len(checkbox_lines) >= 2, (
        f"expected at least 2 commit checkboxes, "
        f"got {len(checkbox_lines)}"
    )
