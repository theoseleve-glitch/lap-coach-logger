"""T229: COACHING_RULES.md exists and explains client-side execution.

Pins the doc -> code contract for the rules-engine architecture
(ADR-009: server authors rules, client executes rules).

Specifically:

  - Doc references ADR-009 — without it, readers can't trace
    why this architecture exists.
  - Doc names the key types from ``rules_engine.py``
    (``RuleBundle``, ``Rule``, ``BundleSource``, the cache
    + HTTP client classes) so a reader can navigate from prose
    to code.
  - Doc lists the bundle-format invariants
    (``schema_version``, ``bundle_id``, ``compiled_at``,
    ``rules``) since those define the wire contract with the
    server.
  - Doc has a "Last reviewed: YYYY-MM-DD" line.

Same drift-prevention pattern as T227 (OVERLAY_PLATFORM.md) and
T228 (SESSION_LIFECYCLE.md): the prose can't silently rot
because the structural references are pinned.
"""
from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOC_PATH = _REPO_ROOT / "COACHING_RULES.md"


def _read_doc() -> str:
    assert _DOC_PATH.exists(), (
        f"missing {_DOC_PATH} — T229 needs the doc written"
    )
    return _DOC_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ADR reference
# ---------------------------------------------------------------------------


def test_doc_references_adr_009() -> None:
    """ADR-009 is the architectural decision behind this whole
    'server-authored, client-executed' design. The doc must
    cite it so readers can find the rationale."""
    doc = _read_doc()
    assert "ADR-009" in doc, (
        "COACHING_RULES.md must reference ADR-009 (rules engine "
        "distribution) — it's the architectural decision that "
        "explains why this client-side execution design exists."
    )


# ---------------------------------------------------------------------------
# Key class references
# ---------------------------------------------------------------------------


def test_doc_names_key_rules_engine_classes() -> None:
    """Doc must name the canonical types from rules_engine.py
    so a reader can navigate from prose to code."""
    doc = _read_doc()
    required = ("RuleBundle", "Rule", "BundleSource")
    missing = [name for name in required if name not in doc]
    assert not missing, (
        f"COACHING_RULES.md is missing required class names: "
        f"{missing}. Each is exported from "
        f"lap_coach_logger.coaching.rules_engine."
    )


def test_doc_explains_bundle_format_fields() -> None:
    """The bundle wire format has 4 required top-level keys
    (schema_version, bundle_id, compiled_at, rules) — the doc
    must list them so server changes can't break the client
    silently. Mirrored from ``_REQUIRED_BUNDLE_FIELDS`` in
    ``rules_engine.py``."""
    doc = _read_doc()
    required = ("schema_version", "bundle_id", "compiled_at", "rules")
    missing = [name for name in required if name not in doc]
    assert not missing, (
        f"COACHING_RULES.md is missing bundle-format fields: "
        f"{missing}. These are the required top-level keys in "
        f"the wire-format JSON."
    )


def test_doc_mentions_client_side_execution_phrase() -> None:
    """Pin the load-bearing phrase in the doc title/intro so
    a casual scan immediately tells the reader what this is."""
    doc = _read_doc().lower()
    # Either phrasing is fine; pin that AT LEAST one appears.
    candidates = ("client-side execution", "client-side", "client executes")
    assert any(c in doc for c in candidates), (
        "COACHING_RULES.md should announce 'client-side' "
        "execution prominently — it's the headline of the doc."
    )


# ---------------------------------------------------------------------------
# Freshness marker
# ---------------------------------------------------------------------------


def test_doc_has_last_reviewed_marker() -> None:
    """Same drift-prevention as T227/T228: explicit date line
    so future readers can spot stale prose at a glance."""
    doc = _read_doc()
    pattern = r"Last reviewed:\s*\d{4}-\d{2}-\d{2}"
    assert re.search(pattern, doc), (
        "COACHING_RULES.md is missing a 'Last reviewed: "
        "YYYY-MM-DD' line. Add one near the top."
    )
