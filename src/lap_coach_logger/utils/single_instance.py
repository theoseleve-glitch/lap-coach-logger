"""Windows single-instance guard based on a named mutex.

Uses a Windows named pipe for restore-window signalling instead of a TCP
socket.  Named pipes are process-local, don't trigger firewall prompts,
and avoid port collisions.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

from lap_coach_logger.app_identity import APP_ID

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_CreateMutexW = _kernel32.CreateMutexW
_CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_CreateMutexW.restype = wintypes.HANDLE

_CloseHandle = _kernel32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL

ERROR_ALREADY_EXISTS = 183

_PIPE_NAME = rf"\\.\pipe\{APP_ID}"
_SIGNAL_TOKEN = b"SHOW"


def notify_existing_instance(timeout_ms: int = 300) -> bool:
    """Ask already-running instance to restore its main window via named pipe."""
    try:
        import win32file  # type: ignore[import-untyped]
        handle = win32file.CreateFile(
            _PIPE_NAME,
            win32file.GENERIC_WRITE,
            0, None,
            win32file.OPEN_EXISTING,
            0, None,
        )
        try:
            win32file.WriteFile(handle, _SIGNAL_TOKEN)
        finally:
            win32file.CloseHandle(handle)
        return True
    except Exception:
        # Fallback: use ctypes if pywin32 is unavailable
        return _notify_via_ctypes()


def _notify_via_ctypes() -> bool:
    """Write to the named pipe using raw Win32 API via ctypes."""
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE = wintypes.HANDLE(-1).value

    handle = _kernel32.CreateFileW(
        _PIPE_NAME, GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None,
    )
    if handle == INVALID_HANDLE:
        return False
    try:
        written = wintypes.DWORD(0)
        _kernel32.WriteFile(
            handle, _SIGNAL_TOKEN, len(_SIGNAL_TOKEN),
            ctypes.byref(written), None,
        )
        return written.value > 0
    finally:
        _CloseHandle(handle)


class InstanceSignalServer:
    """Named-pipe listener that receives SHOW restore requests."""

    def __init__(self, on_show) -> None:  # noqa: ANN001
        self._on_show = on_show
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="instance-signal", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        # Connect to our own pipe to unblock the waiting ConnectNamedPipe call
        try:
            _notify_via_ctypes()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        PIPE_ACCESS_INBOUND = 0x00000001
        PIPE_TYPE_BYTE = 0x00000000
        PIPE_WAIT = 0x00000000
        INVALID_HANDLE = wintypes.HANDLE(-1).value

        while not self._stop.is_set():
            pipe = _kernel32.CreateNamedPipeW(
                _PIPE_NAME,
                PIPE_ACCESS_INBOUND,
                PIPE_TYPE_BYTE | PIPE_WAIT,
                1,     # max instances
                64,    # out buffer
                64,    # in buffer
                0,     # default timeout
                None,  # security
            )
            if pipe == INVALID_HANDLE:
                self._stop.wait(0.5)
                continue

            # Block until a client connects (or we self-connect on stop)
            connected = _kernel32.ConnectNamedPipe(pipe, None)
            if self._stop.is_set():
                _CloseHandle(pipe)
                break

            if connected or ctypes.get_last_error() == 535:  # ERROR_PIPE_CONNECTED
                buf = ctypes.create_string_buffer(16)
                read = wintypes.DWORD(0)
                _kernel32.ReadFile(pipe, buf, 16, ctypes.byref(read), None)
                if buf.value.startswith(_SIGNAL_TOKEN):
                    self._on_show()

            _kernel32.DisconnectNamedPipe(pipe)
            _CloseHandle(pipe)


class SingleInstance:
    """Acquire a named process-wide mutex for single-instance behavior."""

    def __init__(self, name: str | None = None) -> None:
        self._name = name or f"Global\\{APP_ID}"
        self._handle: int | None = None

    def acquire(self) -> bool:
        handle = _CreateMutexW(None, False, self._name)
        if not handle:
            return True
        self._handle = int(handle)
        first = ctypes.get_last_error() != ERROR_ALREADY_EXISTS
        if not first:
            notify_existing_instance()
        return first

    def release(self) -> None:
        if self._handle:
            _CloseHandle(self._handle)
            self._handle = None
