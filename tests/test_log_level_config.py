"""T232: Log level configurable via Settings.

Pins the contract that the user can pick a log level from
Settings and ``setup_logging`` honors it on next launch:

  - ``AppConfig.log_level`` defaults to ``"INFO"``
  - The field round-trips via to_dict / from_dict
  - Old configs without ``log_level`` load silently as ``"INFO"``
  - ``setup_logging(log_level="DEBUG")`` applies DEBUG to the
    root logger; ``setup_logging(log_level="WARNING")`` applies
    WARNING; unknown strings fall back to INFO with a warning
  - ``AppConfig.validate()`` flags unknown log_level strings
  - Legacy ``debug=True`` still works (back-compat with
    bootstrap.py + native_bridge/runtime.py call sites)

Wiring bootstrap.py to actually pass ``config.log_level`` through
is part of GREEN — without it, the Settings value is just data
on disk that no logger reads.
"""
from __future__ import annotations

import logging
from dataclasses import fields

import pytest

from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.utils import logging_setup


# ---------------------------------------------------------------------------
# AppConfig.log_level field shape
# ---------------------------------------------------------------------------


def test_app_config_has_log_level_field() -> None:
    cfg = AppConfig()
    assert hasattr(cfg, "log_level")
    assert isinstance(cfg.log_level, str)


def test_log_level_defaults_to_info() -> None:
    """INFO is the right default — DEBUG would balloon the
    log file under ordinary use; WARNING would hide useful
    diagnostic context."""
    cfg = AppConfig()
    assert cfg.log_level == "INFO"


def test_log_level_listed_in_app_config_fields() -> None:
    field_names = {f.name for f in fields(AppConfig)}
    assert "log_level" in field_names


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------


def test_log_level_round_trips_via_to_dict_from_dict() -> None:
    cfg = AppConfig()
    cfg.log_level = "WARNING"
    payload = cfg.to_dict()
    restored = AppConfig.from_dict(payload)
    assert restored.log_level == "WARNING"


def test_old_config_without_log_level_loads_as_info() -> None:
    """A pre-T232 config has no ``log_level`` field. It must
    silently load as INFO so the upgrade is invisible."""
    payload = {
        "output_dir": "/tmp/test",
        "debug": False,
        # NOTABLY MISSING: log_level
    }
    cfg = AppConfig.from_dict(payload)
    assert cfg.log_level == "INFO"


# ---------------------------------------------------------------------------
# AppConfig.validate
# ---------------------------------------------------------------------------


def test_validate_accepts_standard_log_levels() -> None:
    """The five standard logging levels must all validate."""
    for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        cfg = AppConfig()
        cfg.log_level = level
        errors = cfg.validate()
        assert not any("log_level" in e for e in errors), (
            f"validate() rejected standard level {level!r}: {errors}"
        )


def test_validate_rejects_unknown_log_level() -> None:
    """An unknown log_level (typo, malicious config) must be
    flagged so the user sees a clear error rather than silent
    fallback to default."""
    cfg = AppConfig()
    cfg.log_level = "VERBOSE"
    errors = cfg.validate()
    assert any("log_level" in e for e in errors), (
        f"validate() did not flag unknown level 'VERBOSE': {errors}"
    )


# ---------------------------------------------------------------------------
# setup_logging applies the level
# ---------------------------------------------------------------------------


def test_setup_logging_with_explicit_debug_level(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(logging_setup, "logs_dir", lambda: tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    root.handlers.clear()
    try:
        logging_setup.setup_logging(log_level="DEBUG")
        assert root.level == logging.DEBUG
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)


def test_setup_logging_with_explicit_warning_level(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(logging_setup, "logs_dir", lambda: tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    root.handlers.clear()
    try:
        logging_setup.setup_logging(log_level="WARNING")
        assert root.level == logging.WARNING
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)


def test_setup_logging_unknown_level_falls_back_to_info(
    tmp_path, monkeypatch, caplog
) -> None:
    """An unknown level string must NOT crash setup_logging —
    it falls back to INFO with a warning so the user gets a
    working app even with a malformed config."""
    monkeypatch.setattr(logging_setup, "logs_dir", lambda: tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    root.handlers.clear()
    try:
        # Must not raise:
        logging_setup.setup_logging(log_level="VERBOSE")
        assert root.level == logging.INFO
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)


# ---------------------------------------------------------------------------
# Back-compat: legacy debug=True still works
# ---------------------------------------------------------------------------


def test_setup_logging_legacy_debug_flag_still_works(tmp_path, monkeypatch) -> None:
    """bootstrap.py + native_bridge/runtime.py both call
    ``setup_logging(debug=config.debug)`` today. That call site
    must keep working until/unless we explicitly migrate them."""
    monkeypatch.setattr(logging_setup, "logs_dir", lambda: tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    root.handlers.clear()
    try:
        logging_setup.setup_logging(debug=True)
        assert root.level == logging.DEBUG
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)


def test_log_level_takes_precedence_over_debug_flag(tmp_path, monkeypatch) -> None:
    """When both are passed, the explicit log_level wins —
    bootstrap.py can pass both during migration without
    surprising behavior."""
    monkeypatch.setattr(logging_setup, "logs_dir", lambda: tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    root.handlers.clear()
    try:
        logging_setup.setup_logging(debug=True, log_level="ERROR")
        assert root.level == logging.ERROR
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved:
            root.addHandler(h)
        root.setLevel(saved_level)
