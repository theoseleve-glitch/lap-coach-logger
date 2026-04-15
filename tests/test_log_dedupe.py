"""Tests for log deduplication filter."""
from __future__ import annotations

import logging
import time
from io import StringIO

from lap_coach_logger.utils.log_dedupe import DedupFilter


def _make_logger(filter_instance: DedupFilter) -> tuple[logging.Logger, StringIO]:
    logger = logging.getLogger(f"test_dedupe_{id(filter_instance)}")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(filter_instance)
    logger.addHandler(handler)
    logger.propagate = False
    return logger, stream


def test_first_error_passes_through():
    f = DedupFilter(window_s=30.0)
    logger, stream = _make_logger(f)
    try:
        raise ValueError("boom")
    except ValueError:
        logger.critical("Unhandled", exc_info=True)
    assert "boom" in stream.getvalue()


def test_duplicate_errors_suppressed():
    f = DedupFilter(window_s=30.0)
    logger, stream = _make_logger(f)
    for _ in range(5):
        try:
            raise ValueError("boom")
        except ValueError:
            logger.critical("Unhandled", exc_info=True)
    output = stream.getvalue()
    # The first traceback should appear once. The others should be suppressed.
    # (A single Python traceback naturally contains the exception type twice:
    # once in the source line and once in the summary, so count "Traceback".)
    assert output.count("Traceback") <= 1


def test_different_errors_not_suppressed():
    f = DedupFilter(window_s=30.0)
    logger, stream = _make_logger(f)
    for msg in ["alpha", "beta", "gamma"]:
        try:
            raise ValueError(msg)
        except ValueError:
            logger.critical("Unhandled", exc_info=True)
    output = stream.getvalue()
    for msg in ["alpha", "beta", "gamma"]:
        assert msg in output


def test_window_expiry_emits_summary():
    # Helper ensures the raise happens from the same source line each call, so
    # the dedup signature (type + message + top frames) is stable across calls.
    def _boom(logger):
        try:
            raise ValueError("boom")
        except ValueError:
            logger.critical("err", exc_info=True)

    f = DedupFilter(window_s=0.1)  # short window for test
    logger, stream = _make_logger(f)
    _boom(logger)  # first — passes through
    # Fill window with duplicates (suppressed)
    for _ in range(5):
        _boom(logger)
    time.sleep(0.15)
    # Next occurrence after window expiry should emit summary
    _boom(logger)
    output = stream.getvalue()
    assert "Repeated error suppressed" in output


def test_non_exception_logs_pass():
    f = DedupFilter(window_s=30.0)
    logger, stream = _make_logger(f)
    logger.info("hello")
    logger.info("hello")
    logger.info("hello")
    output = stream.getvalue()
    assert output.count("hello") == 3


def test_thread_safety_no_crash():
    import threading
    f = DedupFilter(window_s=30.0)
    logger, stream = _make_logger(f)

    def worker():
        for _ in range(100):
            try:
                raise ValueError("boom")
            except ValueError:
                logger.critical("Unhandled", exc_info=True)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # All calls completed without crash; most were deduped
    snapshot = f.snapshot()
    assert len(snapshot) >= 1


def test_reset_clears_state():
    f = DedupFilter(window_s=30.0)
    logger, _ = _make_logger(f)
    try:
        raise ValueError("boom")
    except ValueError:
        logger.critical("x", exc_info=True)
    assert len(f.snapshot()) == 1
    f.reset()
    assert len(f.snapshot()) == 0


def test_configurable_window():
    f = DedupFilter(window_s=5.0)
    assert f.window_s == 5.0
    f.set_window(10.0)
    assert f.window_s == 10.0
