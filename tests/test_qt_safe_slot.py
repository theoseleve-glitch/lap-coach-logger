"""Tests for safe_slot decorator."""
from __future__ import annotations

import logging

from lap_coach_logger.utils.qt_safe_slot import safe_slot


class TestSafeSlot:

    def test_normal_call_returns_value(self):
        @safe_slot()
        def my_slot(self, x):
            return x * 2
        assert my_slot(None, 5) == 10

    def test_exception_caught_and_returns_none(self, caplog):
        @safe_slot()
        def my_slot(self):
            raise ValueError("boom")
        with caplog.at_level(logging.WARNING):
            result = my_slot(None)
        assert result is None
        assert any("boom" in r.message for r in caplog.records)

    def test_log_includes_function_name(self, caplog):
        @safe_slot()
        def my_specific_slot(self):
            raise RuntimeError("xyz")
        with caplog.at_level(logging.WARNING):
            my_specific_slot(None)
        assert any("my_specific_slot" in r.message for r in caplog.records)

    def test_log_includes_exception_type(self, caplog):
        @safe_slot()
        def my_slot(self):
            raise KeyError("missing")
        with caplog.at_level(logging.WARNING):
            my_slot(None)
        assert any("KeyError" in r.message for r in caplog.records)

    def test_snapshot_keys_extracted_from_dict_arg(self, caplog):
        @safe_slot()
        def my_slot(self, snap):
            raise ValueError("x")
        with caplog.at_level(logging.WARNING):
            my_slot(None, {"alpha": 1, "beta": 2, "gamma": 3})
        log_text = "\n".join(r.message for r in caplog.records)
        assert "alpha" in log_text
        assert "beta" in log_text

    def test_non_dict_args_produce_empty_keys(self, caplog):
        @safe_slot()
        def my_slot(self, x):
            raise ValueError("x")
        with caplog.at_level(logging.WARNING):
            my_slot(None, 42)
        log_text = "\n".join(r.message for r in caplog.records)
        assert "snapshot_keys=[]" in log_text

    def test_no_reraise_from_exception(self):
        @safe_slot()
        def my_slot(self):
            raise RuntimeError("should not propagate")
        # Must not raise
        my_slot(None)

    def test_traceback_truncated(self, caplog):
        # Deep recursion then raise
        def recurse(n):
            if n <= 0:
                raise ValueError("deep")
            recurse(n - 1)

        @safe_slot()
        def my_slot(self):
            recurse(50)

        with caplog.at_level(logging.WARNING):
            my_slot(None)
        log_text = "\n".join(r.message for r in caplog.records)
        # We limit to 5 frames - count occurrences of 'recurse' should be bounded
        assert log_text.count("recurse") <= 10  # generous upper bound


class TestKwargSnapshot:

    def test_dict_in_kwargs(self, caplog):
        @safe_slot()
        def my_slot(self, **kw):
            raise ValueError("x")
        with caplog.at_level(logging.WARNING):
            my_slot(None, snap={"k1": 1, "k2": 2})
        log_text = "\n".join(r.message for r in caplog.records)
        assert "k1" in log_text
