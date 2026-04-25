"""T176: PyInstaller spec file is parseable Python.

The PyInstaller spec is just a Python file evaluated by
``pyinstaller`` at build time. If a stash/rebase mistake leaves
unresolved merge conflict markers (``<<<<<<<``, ``=======``,
``>>>>>>>``) in the file, ``pyinstaller`` raises ``SyntaxError``
and the release build fails — silently to anyone who isn't
running the build pipeline.

T176 pins two cheap properties:

1. The spec file contains no git merge conflict markers.
2. The spec file is syntactically valid Python (parses with
   :func:`ast.parse`). PyInstaller globals like ``SPECPATH``,
   ``Analysis``, ``EXE`` are runtime-injected, so we can't
   import the spec, but we can confirm the AST is clean.

Source-content + AST pin (consistent with T156-T175 source pins).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SPEC_PATH = Path(__file__).resolve().parents[1] / "lap_coach_logger.spec"


@pytest.fixture(scope="module")
def spec_text() -> str:
    return _SPEC_PATH.read_text(encoding="utf-8")


def test_spec_has_no_merge_conflict_markers(spec_text: str) -> None:
    """No leftover ``<<<<<<<`` / ``=======`` / ``>>>>>>>``.
    These crash pyinstaller at build time with a SyntaxError far
    from the actual location of the merge conflict."""
    forbidden = ("<<<<<<<", ">>>>>>>")
    # `=======` (7+ equals) is the merge midline. We exclude
    # the more common `============` divider strings used in
    # comments by requiring it to be ON ITS OWN LINE.
    for line in spec_text.splitlines():
        if line.strip().startswith("======="):
            pytest.fail(
                f"spec file has merge conflict midline marker: "
                f"{line!r}"
            )
    for marker in forbidden:
        assert marker not in spec_text, (
            f"spec file contains git merge conflict marker {marker!r}"
        )


def test_spec_is_valid_python(spec_text: str) -> None:
    """``pyinstaller`` evaluates the spec file as Python.
    A SyntaxError here means the build fails."""
    try:
        ast.parse(spec_text, filename=str(_SPEC_PATH))
    except SyntaxError as exc:
        pytest.fail(
            f"spec file does not parse as valid Python: {exc}"
        )
