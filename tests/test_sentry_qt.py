"""T057: Qt → Sentry message forwarding.

QML errors don't raise Python exceptions — they emit Qt log
messages at ``QtCriticalMsg`` / ``QtFatalMsg`` severity, which
``sys.excepthook`` (Sentry's default) never sees. To get QML throws
into Sentry we install a global ``qInstallMessageHandler`` that
forwards critical+ messages to ``sentry_sdk.capture_message`` while
also routing everything through Python ``logging`` so file logs
still see Qt diagnostics.

The ``make_qt_message_handler`` factory returns the closure as a
plain callable so tests can drive it with synthetic inputs without
installing a real handler (which would leak across the suite).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pytest

from PySide6.QtCore import QtMsgType


@dataclass
class _FakeContext:
    """Stand-in for Qt's QMessageLogContext for handler unit tests."""

    file: str | None = None
    line: int = 0
    function: str | None = None
    category: str | None = None


# ---------------------------------------------------------------------------
# Forwarding decisions
# ---------------------------------------------------------------------------


def test_critical_message_is_forwarded_to_sentry() -> None:
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    captured: list[str] = []
    handler = make_qt_message_handler(sentry_capture=captured.append)

    handler(
        QtMsgType.QtCriticalMsg,
        _FakeContext(file="MainWindow.qml", line=42),
        "TypeError: cannot read property 'x' of undefined",
    )

    assert len(captured) == 1
    assert "TypeError: cannot read property 'x' of undefined" in captured[0]
    assert "MainWindow.qml:42" in captured[0]


def test_fatal_message_is_forwarded_to_sentry() -> None:
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    captured: list[str] = []
    handler = make_qt_message_handler(sentry_capture=captured.append)

    handler(
        QtMsgType.QtFatalMsg,
        _FakeContext(file="x.qml", line=1),
        "fatal: scene graph aborted",
    )

    assert len(captured) == 1
    assert "fatal: scene graph aborted" in captured[0]


@pytest.mark.parametrize(
    "msg_type", [QtMsgType.QtDebugMsg, QtMsgType.QtInfoMsg, QtMsgType.QtWarningMsg]
)
def test_low_severity_messages_are_not_forwarded_to_sentry(
    msg_type: QtMsgType,
) -> None:
    """Warnings about deprecated property bindings would drown signal."""
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    captured: list[str] = []
    handler = make_qt_message_handler(sentry_capture=captured.append)

    handler(msg_type, _FakeContext(), "noisy diagnostic")

    assert captured == []


def test_handler_works_when_sentry_capture_is_none() -> None:
    """Sentry init may have failed (no DSN) — handler still routes
    to logging without exploding."""
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    handler = make_qt_message_handler(sentry_capture=None)

    # Must not raise on any severity.
    handler(QtMsgType.QtCriticalMsg, _FakeContext(), "critical")
    handler(QtMsgType.QtWarningMsg, _FakeContext(), "warning")


# ---------------------------------------------------------------------------
# Logging routing — Qt messages reach the file log via Python logging
# ---------------------------------------------------------------------------


def test_critical_qt_message_is_logged_at_error_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    handler = make_qt_message_handler(sentry_capture=None)
    with caplog.at_level(logging.ERROR, logger="qt"):
        handler(
            QtMsgType.QtCriticalMsg,
            _FakeContext(file="X.qml", line=3),
            "boom",
        )

    assert any(
        "boom" in r.getMessage() and r.levelno == logging.ERROR for r in caplog.records
    )


def test_warning_qt_message_is_logged_at_warning_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    handler = make_qt_message_handler(sentry_capture=None)
    with caplog.at_level(logging.WARNING, logger="qt"):
        handler(QtMsgType.QtWarningMsg, _FakeContext(), "deprecation: foo")

    assert any(
        "deprecation: foo" in r.getMessage() and r.levelno == logging.WARNING
        for r in caplog.records
    )


def test_fatal_qt_message_is_logged_at_critical_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    handler = make_qt_message_handler(sentry_capture=None)
    with caplog.at_level(logging.CRITICAL, logger="qt"):
        handler(QtMsgType.QtFatalMsg, _FakeContext(), "fatal: bye")

    assert any(
        "fatal: bye" in r.getMessage() and r.levelno == logging.CRITICAL
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Robustness — context fields can be missing
# ---------------------------------------------------------------------------


def test_handler_tolerates_context_without_file_info() -> None:
    """Synthetic Qt contexts (e.g. messages emitted from C++) often
    have empty ``file`` / ``line``; the formatter must not crash."""
    from lap_coach_logger.utils.sentry_qt import make_qt_message_handler

    captured: list[str] = []
    handler = make_qt_message_handler(sentry_capture=captured.append)

    handler(QtMsgType.QtCriticalMsg, _FakeContext(file=None, line=0), "no source")

    assert captured == ["no source"]


# ---------------------------------------------------------------------------
# Installation — calls Qt API only when sentry_capture is wired up
# ---------------------------------------------------------------------------


def test_install_passes_handler_to_qinstallmessagehandler() -> None:
    from lap_coach_logger.utils.sentry_qt import install_qt_message_handler

    installed: list[Any] = []

    def fake_install(handler: Any) -> Any:
        installed.append(handler)
        return None

    captured: list[str] = []
    result = install_qt_message_handler(
        sentry_capture=captured.append, qt_install_fn=fake_install
    )

    assert result is True
    assert len(installed) == 1
    assert callable(installed[0])
    # Smoke-test: the installed handler forwards critical to our recorder.
    installed[0](QtMsgType.QtCriticalMsg, _FakeContext(), "boom")
    assert "boom" in captured[0]


def test_install_is_a_noop_when_sentry_capture_is_none() -> None:
    """If init_sentry returned False, there's no point installing the
    forwarder — Qt's default stderr handler keeps working as-is."""
    from lap_coach_logger.utils.sentry_qt import install_qt_message_handler

    installed: list[Any] = []

    def fake_install(handler: Any) -> Any:
        installed.append(handler)
        return None

    result = install_qt_message_handler(
        sentry_capture=None, qt_install_fn=fake_install
    )

    assert result is False
    assert installed == []
