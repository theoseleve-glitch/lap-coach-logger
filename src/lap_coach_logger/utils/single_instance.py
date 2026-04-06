"""Windows single-instance guard based on a named mutex."""

from __future__ import annotations

import ctypes
import socket
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
_SIGNAL_HOST = "127.0.0.1"
_SIGNAL_TOKEN = b"SHOW"


def _signal_port() -> int:
    # Stable app-specific port in a high non-privileged range.
    return 42000 + (sum(APP_ID.encode("utf-8")) % 1000)


def notify_existing_instance(timeout_s: float = 0.3) -> bool:
    """Ask already-running instance to restore its main window."""
    try:
        with socket.create_connection((_SIGNAL_HOST, _signal_port()), timeout=timeout_s) as sock:
            sock.sendall(_SIGNAL_TOKEN)
        return True
    except OSError:
        return False


class InstanceSignalServer:
    """Lightweight localhost listener that receives SHOW restore requests."""

    def __init__(self, on_show) -> None:  # noqa: ANN001
        self._on_show = on_show
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._sock: socket.socket | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="instance-signal", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock = sock
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((_SIGNAL_HOST, _signal_port()))
            sock.listen(5)
            sock.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    conn, _addr = sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    try:
                        data = conn.recv(16)
                        if data.startswith(_SIGNAL_TOKEN):
                            self._on_show()
                    except OSError:
                        continue
        finally:
            try:
                sock.close()
            except OSError:
                pass


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
