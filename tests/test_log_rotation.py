"""T231: Log rotation pinned at 10 MB / 7 backups.

Pins the rotation contract so the operational footprint of
the log directory stays bounded:

  - 10 MB per file (so a single Sentry-style cascade can't
    fill the disk in seconds)
  - 7 backups kept (one week of post-mortems if rotation
    triggers daily; longer if traffic is light)

The numbers come from the sprint roadmap (T231). Changing
either side without bumping these tests is a deliberate
opt-out, not a silent drift.

Both the module-level constants AND the handler that gets
installed on the root logger are pinned, so a refactor that
moves the constants but forgets to wire them is caught.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from lap_coach_logger.utils import logging_setup


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


def test_max_bytes_is_ten_megabytes() -> None:
    """Pinned to 10 MB exactly — bigger files mean more lost
    context per rotation; smaller means more frequent IO churn."""
    assert logging_setup._MAX_BYTES == 10 * 1024 * 1024


def test_backup_count_is_seven() -> None:
    """Pinned to 7 — enough history that a Monday morning
    triage can see Friday's incident, but not so many that the
    log directory dominates disk usage."""
    assert logging_setup._BACKUP_COUNT == 7


# ---------------------------------------------------------------------------
# Wiring: the actual handler installed on root must use these constants
# ---------------------------------------------------------------------------


def test_root_logger_rotating_handler_uses_ten_mb_limit(
    tmp_path, monkeypatch
) -> None:
    """The handler installed by setup_logging() must use the
    10 MB limit. Pinning the constants is necessary but not
    sufficient — a refactor could land the new constants in
    the file but forget to wire them through to RotatingFileHandler."""
    # Redirect logs_dir() so the test doesn't pollute the real
    # log directory.
    monkeypatch.setattr(
        logging_setup, "logs_dir", lambda: tmp_path
    )
    # Reset the root logger so setup_logging actually runs
    # (it returns early if handlers already exist).
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    root.handlers.clear()
    try:
        logging_setup.setup_logging(debug=False)
        rotating = next(
            (h for h in root.handlers if isinstance(h, RotatingFileHandler)),
            None,
        )
        assert rotating is not None, (
            "setup_logging() did not install a RotatingFileHandler"
        )
        assert rotating.maxBytes == 10 * 1024 * 1024, (
            f"RotatingFileHandler.maxBytes is {rotating.maxBytes}, "
            f"expected 10 MB (T231 contract)"
        )
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved_handlers:
            root.addHandler(h)


def test_root_logger_rotating_handler_keeps_seven_backups(
    tmp_path, monkeypatch
) -> None:
    """Same pin as the size check — the wiring not the
    constant is the load-bearing assertion."""
    monkeypatch.setattr(
        logging_setup, "logs_dir", lambda: tmp_path
    )
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    root.handlers.clear()
    try:
        logging_setup.setup_logging(debug=False)
        rotating = next(
            (h for h in root.handlers if isinstance(h, RotatingFileHandler)),
            None,
        )
        assert rotating is not None
        assert rotating.backupCount == 7, (
            f"RotatingFileHandler.backupCount is {rotating.backupCount}, "
            f"expected 7 (T231 contract)"
        )
    finally:
        for h in root.handlers:
            try:
                h.close()
            except Exception:
                pass
        root.handlers.clear()
        for h in saved_handlers:
            root.addHandler(h)


# ---------------------------------------------------------------------------
# Integration: rotation actually triggers when the size threshold is crossed
# ---------------------------------------------------------------------------


def test_rotation_actually_triggers_at_size_threshold(tmp_path) -> None:
    """End-to-end check: when written-bytes exceed maxBytes,
    the handler must rotate the file (creating a .1 backup).
    Catches the regression where Python's RotatingFileHandler
    is silently broken by an integer-overflow or a typo'd
    size constant."""
    log_file = tmp_path / "test.log"
    handler = RotatingFileHandler(
        log_file,
        maxBytes=1024,  # tiny limit so we don't write 10 MB in a test
        backupCount=2,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    test_logger = logging.getLogger("t231_rotation_test")
    test_logger.handlers.clear()
    test_logger.addHandler(handler)
    test_logger.propagate = False
    test_logger.setLevel(logging.INFO)
    try:
        # Each line is ~64 bytes; emit ~30 lines to clearly
        # exceed the 1024-byte threshold and trigger rotation.
        for i in range(30):
            test_logger.info("rotation-trigger-line-%03d-payload-padding", i)
        backup_one = tmp_path / "test.log.1"
        assert backup_one.exists(), (
            "RotatingFileHandler did not create a .1 backup after "
            "exceeding the size threshold"
        )
    finally:
        handler.close()
        test_logger.handlers.clear()
