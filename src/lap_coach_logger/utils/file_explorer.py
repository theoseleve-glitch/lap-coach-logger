"""Cross-platform "reveal in file explorer" helper.

The desktop has multiple seams that want to "open this folder in
the user's file manager" (output dir, logs, config, individual
session bundles). Python's ``os.startfile`` is Windows-only and
silently absent on macOS / Linux, so direct calls fail.

``reveal_in_file_explorer(path)`` dispatches per-platform:

  * Windows     -> ``os.startfile(str(path))``
  * macOS       -> ``subprocess.run(["open", str(path)])``
  * Linux/-like -> ``subprocess.run(["xdg-open", str(path)])``
  * other       -> safe no-op (logs a warning)

Returns ``True`` when a launcher was invoked, ``False`` when the
call was a no-op (path missing, unsupported platform). Tests
inject ``platform`` / ``runner`` / ``startfile_fn`` so coverage
of every branch is hermetic regardless of the host OS.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_Runner = Callable[..., Any]
_StartfileFn = Callable[[str], Any]


def reveal_in_file_explorer(
    path: str | os.PathLike[str],
    *,
    platform: str | None = None,
    runner: _Runner | None = None,
    startfile_fn: _StartfileFn | None = None,
) -> bool:
    """Open ``path`` in the platform-native file manager.

    Returns ``True`` iff a launcher was actually invoked. ``False``
    means the call was a safe no-op — the path didn't exist or the
    host platform isn't recognised.
    """
    target = Path(path)
    if not target.exists():
        log.warning("reveal_in_file_explorer: path %r does not exist", str(target))
        return False

    plat = platform if platform is not None else sys.platform
    target_str = str(target)

    if plat == "win32":
        fn = startfile_fn if startfile_fn is not None else _default_startfile
        if fn is None:
            log.warning("reveal_in_file_explorer: os.startfile unavailable")
            return False
        try:
            fn(target_str)
        except Exception:
            log.exception("reveal_in_file_explorer: os.startfile failed")
            return False
        return True

    if plat == "darwin":
        argv = ["open", target_str]
    elif plat.startswith("linux"):
        argv = ["xdg-open", target_str]
    else:
        log.warning(
            "reveal_in_file_explorer: unsupported platform %r; no-op",
            plat,
        )
        return False

    runner_fn = runner if runner is not None else _default_runner
    try:
        runner_fn(argv, check=False)
    except Exception:
        log.exception("reveal_in_file_explorer: runner failed for %s", argv)
        return False
    return True


def _default_runner(argv: list[str], **kwargs: Any) -> Any:
    """Production runner — ``subprocess.run`` with safe defaults."""
    return subprocess.run(argv, **kwargs)


def _default_startfile(path: str) -> None:
    """Production Windows entry point — re-exposed for injectability."""
    # ``os.startfile`` only exists on win32. We import lazily inside
    # the wrapper so non-Windows hosts can still load this module.
    startfile = getattr(os, "startfile", None)
    if startfile is None:
        raise RuntimeError("os.startfile is not available on this platform")
    startfile(path)


__all__ = ["reveal_in_file_explorer"]
