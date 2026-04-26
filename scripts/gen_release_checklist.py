"""T183: auto-generate a release checklist from git log between
two refs (typically tags).

Usage::

    python scripts/gen_release_checklist.py <from_ref> <to_ref> [--version X.Y.Z]

Outputs a markdown checklist to stdout. Each commit becomes a
``- [ ] <sha> <subject>`` checkbox so the release manager can
tick each off after manual review. A footer of standard
pre-release gates (pytest, installer build, smoke test, tag) is
appended so they don't get forgotten between releases.

Pure formatter (``format_checklist``) is split from the
subprocess-shelling helper (``git_commits_between``) so unit
tests can pin the markdown contract without needing real git
history.
"""
from __future__ import annotations

import argparse
import dataclasses
import subprocess
import sys
from pathlib import Path


@dataclasses.dataclass(frozen=True)
class Commit:
    """One commit in the release range. ``sha`` is the short
    hash (git ``%h``); ``subject`` is the first line of the
    commit message (git ``%s``)."""

    sha: str
    subject: str


def git_commits_between(
    from_ref: str,
    to_ref: str,
    *,
    repo_root: Path | None = None,
) -> list[Commit]:
    """Return commits in the range ``from_ref..to_ref``.

    Order matches ``git log`` default (newest first). Raises
    ``CalledProcessError`` if either ref is invalid — caller
    can surface this as a clean CLI error.
    """
    cmd = [
        "git", "log",
        "--pretty=format:%h\t%s",
        f"{from_ref}..{to_ref}",
    ]
    # T200: ``errors="replace"`` so commit messages with
    # non-UTF-8 bytes (e.g., em-dashes encoded as cp1252 on
    # Windows) don't crash the script with a UnicodeDecodeError.
    # The replacement char ``�`` is acceptable in a
    # release-notes file; raising would block the pipeline.
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )
    commits: list[Commit] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append(Commit(sha=sha, subject=subject))
    return commits


def format_checklist(
    commits: list[Commit],
    *,
    from_ref: str,
    to_ref: str,
    version: str | None = None,
) -> str:
    """Format ``commits`` as a markdown release checklist.

    ``version`` (when supplied) is included in the H1 title so
    the checklist is self-identifying when committed to a
    release-notes folder.
    """
    if version:
        title = f"# Release Checklist: v{version}"
    else:
        title = f"# Release Checklist: {from_ref}..{to_ref}"

    lines: list[str] = [
        title,
        "",
        f"_Auto-generated from `git log {from_ref}..{to_ref}`._",
        "",
        "## Commits",
        "",
    ]
    if not commits:
        lines.append("_(no commits in range)_")
    else:
        for c in commits:
            lines.append(f"- [ ] {c.sha} {c.subject}")
    lines.extend([
        "",
        "## Pre-release verification",
        "",
        "- [ ] `pytest -q` green (all 19 baseline failures unchanged)",
        "- [ ] `python -m build` produces wheel + sdist",
        "- [ ] `build_installer.bat` produces signed installer",
        "- [ ] Smoke test installer on clean Windows VM",
        "- [ ] Tag release: `git tag v<version> && git push --tags`",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a release checklist from git log "
            "between two refs."
        ),
    )
    parser.add_argument(
        "from_ref",
        help="Git ref (tag/commit) to start the range from.",
    )
    parser.add_argument(
        "to_ref",
        help="Git ref (tag/commit) to end the range at.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Version string (e.g. 2.0.0) to embed in the title.",
    )
    args = parser.parse_args(argv)

    commits = git_commits_between(args.from_ref, args.to_ref)
    sys.stdout.write(format_checklist(
        commits,
        from_ref=args.from_ref,
        to_ref=args.to_ref,
        version=args.version,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
