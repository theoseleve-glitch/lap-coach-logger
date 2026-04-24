"""Regression test: @lap/schemas Python package wired as dep (sprint T021).

Acceptance: ``from lap_schemas.v1 import SessionManifest`` works. Locks
the invariants so future dep reshuffles can't silently break the
contract bridge: the module imports cleanly, ``SessionManifest`` is a
Pydantic model, and the v1 namespace re-exports the core bundle types
the desktop finalizer / writer layer will rely on.
"""
from __future__ import annotations

import importlib


def test_session_manifest_importable_from_v1_namespace() -> None:
    module = importlib.import_module("lap_schemas.v1")
    assert hasattr(module, "SessionManifest"), (
        "lap_schemas.v1 must re-export SessionManifest"
    )


def test_session_manifest_is_pydantic_model() -> None:
    from pydantic import BaseModel

    from lap_schemas.v1 import SessionManifest

    assert issubclass(SessionManifest, BaseModel)


def test_v1_namespace_exposes_core_types() -> None:
    from lap_schemas import v1

    # Minimal set the desktop bundle pipeline needs (T022-T034).
    for name in ("SessionManifest", "LapRecord", "TelemetrySample"):
        assert hasattr(v1, name), f"lap_schemas.v1 missing re-export: {name}"
