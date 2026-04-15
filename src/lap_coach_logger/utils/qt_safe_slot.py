"""Safe Qt slot decorator.

Wraps @Slot methods so exceptions inside slots are caught, logged
with structured context, and never propagate to Qt's C++ signal
dispatcher (which can cause undefined behavior or cryptic tracebacks).

Usage:
    from PySide6.QtCore import Slot
    from lap_coach_logger.utils.qt_safe_slot import safe_slot

    @safe_slot()
    @Slot(dict)
    def my_slot(self, snap: dict) -> None:
        ...

Or combined:
    @safe_slot(types=(dict,))
    def my_slot(self, snap: dict) -> None:
        ...
"""
from __future__ import annotations

import functools
import logging
import traceback
from typing import Any, Callable

log = logging.getLogger(__name__)

_TRACEBACK_LIMIT = 5


def safe_slot(
    types: tuple[type, ...] | None = None,
    result: type | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory for exception-safe Qt slots.

    If types is provided, this wraps the function with @Slot(*types, result=result)
    from PySide6. Otherwise the wrapped function is returned as-is (caller can
    apply @Slot separately).

    Regardless, all exceptions raised inside the wrapped function are caught,
    logged with:
    - exception type + message
    - limited traceback (top 5 frames)
    - method name
    - any dict-like first positional arg shows its top-level keys (not values)
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - intentional broad catch
                _log_slot_error(fn, exc, args, kwargs)
                # Don't re-raise - Qt slots should never propagate
                return None

        # Optionally attach @Slot
        if types is not None:
            try:
                from PySide6.QtCore import Slot
                slot_kwargs = {}
                if result is not None:
                    slot_kwargs["result"] = result
                return Slot(*types, **slot_kwargs)(wrapper)
            except ImportError:
                # Qt not available (tests, CI without Qt)
                pass
        return wrapper

    return decorator


def _log_slot_error(
    fn: Callable[..., Any],
    exc: BaseException,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    """Structured error log - single-line summary + limited traceback."""
    fn_name = getattr(fn, "__qualname__", getattr(fn, "__name__", "<unknown>"))
    exc_type = type(exc).__name__
    exc_msg = str(exc) or "(no message)"
    snapshot_keys = _extract_snapshot_keys(args, kwargs)
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__, limit=_TRACEBACK_LIMIT)
    tb_text = "".join(tb_lines).rstrip()
    log.warning(
        "Slot %s raised %s: %s | snapshot_keys=%s\n%s",
        fn_name, exc_type, exc_msg, snapshot_keys, tb_text,
    )


def _extract_snapshot_keys(args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[str]:
    """Return top-level keys of the first dict-like positional arg (not values)."""
    # Skip self (first positional arg for methods)
    candidates = list(args[1:]) + list(kwargs.values())
    for arg in candidates:
        if isinstance(arg, dict):
            return sorted(arg.keys())
    return []
