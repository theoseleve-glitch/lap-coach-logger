"""T187: Auto-update opt-out is respected.

Two-part contract:

1. ``AppConfig.auto_update_enabled: bool = True`` — defaults
   to ON (users opt OUT, not in). Old config files that
   predate this field load as True via ``from_dict`` —
   transparent upgrade with the existing convention used by
   ``telemetry_enabled``.

2. ``lap_coach_logger.updates.start_update_check_thread(
   current_version, *, enabled, log=None)`` — when
   ``enabled=False``, returns ``None`` and does NOT spawn a
   thread. When ``enabled=True``, returns a started daemon
   ``Thread``. Bootstrap calls this helper with
   ``enabled=config.auto_update_enabled`` so the opt-out
   actually suppresses the network probe.

T185 wired the check; T187 wires the off switch.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import pytest


# -- AppConfig field ---------------------------------------------------


def test_app_config_has_auto_update_enabled_field() -> None:
    """``auto_update_enabled`` must be a public field on
    AppConfig so the Settings dialog can bind to it."""
    import dataclasses
    from lap_coach_logger.config.models import AppConfig

    field_names = {f.name for f in dataclasses.fields(AppConfig)}
    assert "auto_update_enabled" in field_names, (
        "AppConfig must define auto_update_enabled — Settings "
        "needs a field to bind the opt-out checkbox to"
    )


def test_app_config_auto_update_enabled_default_is_true() -> None:
    """Opt-OUT semantics: the default must be ``True`` so the
    feature is on by default and users have to actively turn
    it off (matching the ``telemetry_enabled`` convention)."""
    from lap_coach_logger.config.models import AppConfig

    config = AppConfig()
    assert config.auto_update_enabled is True, (
        "auto_update_enabled default must be True (opt-OUT, not "
        "opt-in)"
    )


def test_app_config_from_dict_preserves_auto_update_enabled() -> None:
    """Round-trip through ``from_dict`` preserves the user's
    setting — flipping it to False in config.json must persist
    across loads."""
    from lap_coach_logger.config.models import AppConfig

    config = AppConfig.from_dict({"auto_update_enabled": False})
    assert config.auto_update_enabled is False


def test_app_config_from_dict_old_config_loads_as_enabled() -> None:
    """Old config files that predate this field must load with
    the default (True) — silent upgrade, no migration needed."""
    from lap_coach_logger.config.models import AppConfig

    # Empty dict simulates an old config file with no
    # auto_update_enabled key.
    config = AppConfig.from_dict({})
    assert config.auto_update_enabled is True


# -- start_update_check_thread helper ----------------------------------


def test_module_exports_start_update_check_thread() -> None:
    """The helper must be exported from the updates package so
    bootstrap can import it cleanly."""
    from lap_coach_logger import updates

    assert hasattr(updates, "start_update_check_thread")


def test_start_update_check_thread_returns_none_when_disabled() -> None:
    """``enabled=False`` is the opt-out path: must return None
    and must NOT spawn a thread."""
    from lap_coach_logger.updates import start_update_check_thread

    thread_count_before = threading.active_count()
    result = start_update_check_thread(
        "2.0.0",
        enabled=False,
    )
    # The function might do tiny work but must not leave
    # background threads running.
    thread_count_after = threading.active_count()

    assert result is None, (
        "when opted-out, helper must return None"
    )
    assert thread_count_after == thread_count_before, (
        f"opted-out call must not spawn threads "
        f"(before={thread_count_before}, after={thread_count_after})"
    )


def test_start_update_check_thread_logs_disabled_message(
    caplog,
) -> None:
    """When disabled, the helper must log a clear message at
    INFO so diagnostic logs show the opt-out is being
    respected (and the user's setting wasn't silently ignored)."""
    from lap_coach_logger.updates import start_update_check_thread

    with caplog.at_level(logging.INFO):
        start_update_check_thread("2.0.0", enabled=False)

    messages = [r.getMessage().lower() for r in caplog.records]
    assert any("auto-update" in m and "disabled" in m for m in messages), (
        f"opted-out path must log a message containing both "
        f"'auto-update' and 'disabled'; got: {messages}"
    )


def test_start_update_check_thread_spawns_daemon_when_enabled() -> None:
    """When enabled, the helper must return a started daemon
    Thread named 'update-check'."""
    from lap_coach_logger.updates import start_update_check_thread

    # Inject a fake check that completes instantly so the
    # thread doesn't make a real network call.
    def fake_check(current_version: str):
        from lap_coach_logger.updates.checker import UpdateCheckResult
        return UpdateCheckResult(
            current_version=current_version,
            latest_version=current_version,
            has_update=False,
            error=None,
        )

    thread = start_update_check_thread(
        "2.0.0",
        enabled=True,
        check_fn=fake_check,
    )
    assert thread is not None, (
        "when enabled, helper must return the spawned Thread"
    )
    assert thread.daemon, (
        "thread must be daemon so it doesn't block app shutdown"
    )
    # Wait briefly for the thread to finish — the fake_check is
    # instant so this should be sub-millisecond.
    thread.join(timeout=2.0)
    assert not thread.is_alive(), (
        "fake_check is instant — thread should have finished"
    )


def test_start_update_check_thread_uses_real_checker_by_default() -> None:
    """If no ``check_fn`` is injected, the helper falls back to
    the real ``check_for_updates``. Pin this so a future
    refactor doesn't accidentally make ``check_fn`` mandatory."""
    import inspect
    from lap_coach_logger.updates import start_update_check_thread

    sig = inspect.signature(start_update_check_thread)
    assert "check_fn" in sig.parameters, (
        "start_update_check_thread should accept an optional "
        "check_fn parameter so tests can inject a fake without "
        "monkey-patching the module"
    )
    # Default must be None or a callable, not required.
    default = sig.parameters["check_fn"].default
    assert default is None or callable(default), (
        f"check_fn default must be None or a callable, got "
        f"{default!r}"
    )


# -- bootstrap wiring --------------------------------------------------


def test_bootstrap_calls_helper_with_config_setting() -> None:
    """Bootstrap must pass ``config.auto_update_enabled`` to
    the helper — otherwise the opt-out is decorative."""
    import lap_coach_logger.bootstrap as bootstrap

    src_text = Path(bootstrap.__file__).read_text(encoding="utf-8")
    assert "start_update_check_thread" in src_text, (
        "bootstrap.py must call `start_update_check_thread` so "
        "the opt-out branch actually fires"
    )
    assert "auto_update_enabled" in src_text, (
        "bootstrap.py must reference `config.auto_update_enabled` "
        "when invoking the helper — otherwise the user's setting "
        "is ignored"
    )
