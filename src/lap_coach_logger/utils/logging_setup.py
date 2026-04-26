"""Centralised logging configuration with rotating file handler.

Call ``setup_logging()`` once at app startup. All modules then use the
standard ``logging.getLogger(__name__)`` pattern.
"""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from lap_coach_logger.utils.log_dedupe import DedupFilter
from lap_coach_logger.utils.paths import logs_dir


_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file (T231)
_BACKUP_COUNT = 7  # one week of post-mortems if rotation triggers daily (T231)


_VALID_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logging(
    *,
    debug: bool = False,
    log_level: str | None = None,
) -> None:
    """Configure root logger with file + stderr handlers.

    Level resolution (T232):
      - explicit ``log_level=...`` (case-insensitive string) wins
      - else fall back to legacy ``debug=True → DEBUG`` /
        ``debug=False → INFO``
      - unknown ``log_level`` strings fall back to INFO with a
        warning so a malformed config doesn't crash the app
    """
    if log_level is not None:
        level = _VALID_LEVELS.get(log_level.upper())
        if level is None:
            # Configure handlers first so the warning we emit
            # below actually goes somewhere.
            level = logging.INFO
            _bad_level = log_level
        else:
            _bad_level = None
    else:
        level = logging.DEBUG if debug else logging.INFO
        _bad_level = None
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if root.handlers:
        return

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Rotating file handler
    log_file = logs_dir() / "lap_coach_logger.log"
    fh = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setLevel(level)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Stderr handler (visible in console during dev, suppressed in windowed exe)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(level)
    sh.setFormatter(formatter)
    root.addHandler(sh)

    # Quieten noisy third-party loggers
    for name in ("PIL", "pyarrow", "pystray", "PySide6", "PySide6.QtDBus"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Install dedupe filter on each handler so propagated records from
    # child loggers (e.g. "unhandled") also flow through the filter.
    # Filters on the root logger itself only apply to records emitted
    # directly on the root logger, not propagated ones.
    dedupe = DedupFilter(window_s=30.0)
    fh.addFilter(dedupe)
    sh.addFilter(dedupe)

    _install_global_exception_logging()

    if _bad_level is not None:
        # Now that the file + stderr handlers are wired, surface
        # the bad-config-input warning where it'll actually be
        # seen instead of silently dropping it.
        logging.getLogger(__name__).warning(
            "Unknown log_level=%r; falling back to INFO. "
            "Valid values: %s",
            _bad_level,
            sorted(_VALID_LEVELS.keys()),
        )


def _is_qt_dispatch_exception(exc_traceback: object) -> bool:
    """Heuristic: is this exception coming from inside Qt's signal dispatch?

    Signal-dispatch exceptions are caught by Qt internally, but Python's
    excepthook still sees them on the currently-executing thread. They
    typically route through qml_bootstrap.py lambdas that connect signals
    to slots. These add noise without actionable information.
    """
    import traceback as _tb
    try:
        frames = _tb.extract_tb(exc_traceback)
    except Exception:
        return False
    if not frames:
        return False
    # The top frame (lambda in qml_bootstrap) is a strong signal
    for frame in frames:
        filename = frame.filename or ""
        if filename.endswith("qml_bootstrap.py") and frame.name == "<lambda>":
            return True
    return False


def _install_global_exception_logging() -> None:
    """Capture otherwise-unhandled exceptions into the configured logger."""

    def _sys_hook(exc_type, exc_value, exc_traceback) -> None:  # noqa: ANN001
        if issubclass(exc_type, KeyboardInterrupt):
            return
        # Downgrade exceptions that originate inside Qt's signal dispatch
        # to debug level. These are caught by Qt internally — logging them
        # at CRITICAL drowns out real errors. Detection heuristic: the
        # bottom-most frame is in a Qt/PySide slot dispatcher.
        if _is_qt_dispatch_exception(exc_traceback):
            logging.getLogger("unhandled").debug(
                "Qt dispatch exception",
                exc_info=(exc_type, exc_value, exc_traceback),
            )
            return
        logging.getLogger("unhandled").critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_type and issubclass(args.exc_type, KeyboardInterrupt):
            return
        logging.getLogger("unhandled.thread").critical(
            "Unhandled thread exception",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
