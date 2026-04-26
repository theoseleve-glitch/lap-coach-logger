"""T198: ``docs/USER_GUIDE.md`` reflects the current
architecture — version, sim adapters, structure.

Documentation drift is a slow-burn failure: a contributor adds
a new sim adapter and forgets to update the user guide; six
months later a user asks "does this support [sim]?" and the
docs say no even though the code says yes. T198 catches this
at CI time.

T198 pins:

1. The user guide exists at the canonical path.
2. It mentions the current ``app_identity.VERSION``.
3. It lists every sim adapter present in
   ``src/lap_coach_logger/adapters/``.
4. It starts with an H1 markdown heading.
5. It's non-empty (>500 bytes).

Source-content cross-file pin (consistent with T184 / T193 /
T194's drift-prevention shape).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[1]
_GUIDE_PATH = _REPO / "docs" / "USER_GUIDE.md"
_APP_IDENTITY_PATH = (
    _REPO / "src" / "lap_coach_logger" / "app_identity.py"
)
_ADAPTERS_DIR = _REPO / "src" / "lap_coach_logger" / "adapters"


# Map adapter module names to the user-facing names that
# should appear in the docs. Keys must match the actual
# adapter Python modules.
_ADAPTER_DOC_NAMES = {
    "acc_adapter.py": "ACC",
    "assetto_corsa_adapter.py": "Assetto Corsa",
    "iracing_adapter.py": "iRacing",
    "lmu_adapter.py": "Le Mans Ultimate",
}


@pytest.fixture(scope="module")
def guide_text() -> str:
    assert _GUIDE_PATH.is_file(), (
        f"docs/USER_GUIDE.md must exist at {_GUIDE_PATH}"
    )
    return _GUIDE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_identity_version() -> str:
    text = _APP_IDENTITY_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'^\s*VERSION\s*=\s*[\'"]([^\'"]+)[\'"]',
        text,
        re.MULTILINE,
    )
    assert match is not None
    return match.group(1)


# -- existence + structure pins ---------------------------------------


def test_user_guide_exists() -> None:
    """Canonical path: ``docs/USER_GUIDE.md`` (release
    notes / installer / web all link there)."""
    assert _GUIDE_PATH.is_file(), (
        f"USER_GUIDE.md must exist at {_GUIDE_PATH}"
    )


def test_user_guide_starts_with_h1(guide_text: str) -> None:
    """Markdown H1 ensures GitHub renders a navigable heading
    when the doc is viewed via the file preview."""
    first_nonblank = next(
        (line for line in guide_text.splitlines() if line.strip()),
        "",
    )
    assert first_nonblank.startswith("# "), (
        f"USER_GUIDE.md must start with a markdown H1; "
        f"first non-blank line: {first_nonblank!r}"
    )


def test_user_guide_is_non_empty(guide_text: str) -> None:
    """User guide should be substantive — pin a generous
    floor. A truncated/empty guide is worse than no guide
    because it implies the topic is documented when it isn't."""
    assert len(guide_text) > 500, (
        f"USER_GUIDE.md appears truncated "
        f"({len(guide_text)} chars); a real user guide "
        f"should be at least 500 chars"
    )


# -- version sync -----------------------------------------------------


def test_user_guide_mentions_current_version(
    guide_text: str, app_identity_version: str,
) -> None:
    """Whatever ``app_identity.VERSION`` says, the user guide
    must mention the same literal — typically in the title
    line. Drift here means users reading the docs see one
    version while the About dialog shows another."""
    assert app_identity_version in guide_text, (
        f"USER_GUIDE.md does not mention the current version "
        f"{app_identity_version!r}. The title line "
        f"(`# Lap Coach Logger v...`) must include the "
        f"current `app_identity.VERSION`."
    )


# -- sim adapter coverage ---------------------------------------------


@pytest.mark.parametrize(
    "adapter_module,display_name",
    sorted(_ADAPTER_DOC_NAMES.items()),
)
def test_user_guide_mentions_each_sim_adapter(
    guide_text: str, adapter_module: str, display_name: str,
) -> None:
    """Every adapter present in
    ``src/lap_coach_logger/adapters/`` must have a matching
    user-facing entry in the user guide. Adding a new
    adapter without updating the docs is a real drift bug."""
    # Sanity: the adapter module file exists in the codebase.
    adapter_path = _ADAPTERS_DIR / adapter_module
    assert adapter_path.is_file(), (
        f"precondition: adapter module {adapter_module!r} "
        f"must exist at {adapter_path}"
    )
    assert display_name in guide_text, (
        f"USER_GUIDE.md must mention {display_name!r} "
        f"(corresponding to adapter {adapter_module!r}) — "
        f"the docs must list every sim the code supports"
    )


def test_adapter_doc_names_cover_all_adapter_modules() -> None:
    """Sanity: the ``_ADAPTER_DOC_NAMES`` map must cover every
    adapter module in the source tree. If a new adapter is
    added (e.g., ``rfactor_adapter.py``) but not mapped here,
    the parameterized test above silently passes — the map
    must be exhaustive."""
    actual = {
        p.name for p in _ADAPTERS_DIR.iterdir()
        if p.is_file()
        and p.suffix == ".py"
        and p.name.endswith("_adapter.py")
        and p.name not in {"base.py"}
    }
    mapped = set(_ADAPTER_DOC_NAMES.keys())
    missing_from_map = actual - mapped
    extra_in_map = mapped - actual
    assert not missing_from_map, (
        f"new adapter modules are not mapped in this test's "
        f"_ADAPTER_DOC_NAMES dict (so the user guide check "
        f"won't catch their drift): {sorted(missing_from_map)}. "
        f"Add the mapping at the top of this test file."
    )
    assert not extra_in_map, (
        f"_ADAPTER_DOC_NAMES references adapters that no "
        f"longer exist in the source tree: {sorted(extra_in_map)}. "
        f"Remove the stale mapping."
    )
