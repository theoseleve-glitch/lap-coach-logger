"""Qt → Sentry message bridge.

QML throws and other Qt-internal errors don't raise Python
exceptions — they emit messages on Qt's logging stream at
``QtCriticalMsg`` / ``QtFatalMsg`` severity. ``sys.excepthook``
(Sentry's default capture path) never sees them. To get those
errors into Sentry we install a global message handler via
``QtCore.qInstallMessageHandler`` that:

  * forwards critical+ messages to ``sentry_sdk.capture_message``
    (the caller decides which capture function to inject), and
  * routes every Qt message through Python ``logging`` under the
    ``"qt"`` logger so file logs still see Qt diagnostics at the
    appropriate Python level.

Forwarding is gated to critical / fatal only — the noisy
``QtWarningMsg`` (deprecated property bindings, layout overflows)
would otherwise drown signal in Sentry.

The factory ``make_qt_message_handler`` returns the closure as a
plain callable so unit tests can drive it with synthetic
``(msg_type, context, msg)`` triples without ever installing a
real handler (which would leak across tests).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QtMsgType, qInstallMessageHandler

# The Python ``logging`` level applied to each Qt severity.
_LEVEL_BY_QT_TYPE: dict[QtMsgType, int] = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}

# Severity floor for forwarding to Sentry. Below this we still log
# to Python ``logging`` but don't bother Sentry.
_SENTRY_FORWARD_TYPES = frozenset({QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg})


def make_qt_message_handler(
    *,
    sentry_capture: Callable[[str], None] | None,
) -> Callable[[QtMsgType, Any, str], None]:
    """Build a Qt message handler that forwards critical+ to Sentry.

    Parameters
    ----------
    sentry_capture:
        Callable like ``sentry_sdk.capture_message``. ``None`` is
        valid and means "don't forward to Sentry, just log" — used
        when ``init_sentry()`` returned False but we still want
        Qt messages in the file log.
    """
    log = logging.getLogger("qt")

    def handler(msg_type: QtMsgType, context: Any, msg: str) -> None:
        location = ""
        file_attr = getattr(context, "file", None)
        line_attr = getattr(context, "line", 0) or 0
        if file_attr:
            location = f" ({file_attr}:{line_attr})"
        formatted = f"{msg}{location}"

        log.log(_LEVEL_BY_QT_TYPE.get(msg_type, logging.WARNING), formatted)

        if sentry_capture is not None and msg_type in _SENTRY_FORWARD_TYPES:
            sentry_capture(formatted)

    return handler


def install_qt_message_handler(
    *,
    sentry_capture: Callable[[str], None] | None,
    qt_install_fn: Callable[[Any], Any] | None = None,
) -> bool:
    """Install the Sentry-forwarding handler on the Qt logging stream.

    Returns ``True`` iff a handler was installed. When
    ``sentry_capture`` is ``None`` the install is skipped so Qt's
    default stderr handler keeps working unmodified — this is the
    cheap path for builds where ``init_sentry()`` declined.
    """
    if sentry_capture is None:
        return False
    install = qt_install_fn if qt_install_fn is not None else qInstallMessageHandler
    handler = make_qt_message_handler(sentry_capture=sentry_capture)
    install(handler)
    return True


__all__ = ["install_qt_message_handler", "make_qt_message_handler"]
