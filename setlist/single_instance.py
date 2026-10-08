"""One Windows app per data directory, with activation on repeated launches."""
import ctypes
import hashlib
import os
from pathlib import Path


class Instance:
    def __init__(self, directory):
        key = hashlib.sha256(str(Path(directory).resolve()).casefold().encode()).hexdigest()[:32]
        self.name = 'Local\\Setlist-' + key
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateMutexW', [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p], ctypes.c_void_p),
            ('CreateEventW', [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p], ctypes.c_void_p),
            ('SetEvent', [ctypes.c_void_p], ctypes.c_int),
            ('WaitForSingleObject', [ctypes.c_void_p, ctypes.c_ulong], ctypes.c_ulong),
            ('CloseHandle', [ctypes.c_void_p], ctypes.c_int),
        ):
            fn = getattr(self.kernel, name); fn.argtypes = args; fn.restype = result
        # Create the auto-reset event first so a rapid second launch can signal it
        # before the first window is ready. The signal remains pending.
        self.event = self.kernel.CreateEventW(None, False, False, self.name + '-activate')
        if not self.event: raise ctypes.WinError(ctypes.get_last_error())
        self.mutex = self.kernel.CreateMutexW(None, False, self.name)
        error = ctypes.get_last_error()
        if not self.mutex:
            self.kernel.CloseHandle(self.event)
            raise ctypes.WinError(error)
        self.primary = error != 183  # ERROR_ALREADY_EXISTS

    def activate(self):
        if not self.kernel.SetEvent(self.event): raise ctypes.WinError(ctypes.get_last_error())

    def requested(self):
        return self.kernel.WaitForSingleObject(self.event, 0) == 0

    def close(self):
        for name in ('mutex', 'event'):
            handle = getattr(self, name, None)
            if handle:
                self.kernel.CloseHandle(handle); setattr(self, name, None)


def focus_process(pid):
    """Restore only the visible top-level Setlist window owned by this PID."""
    from ctypes import wintypes
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsIconic.argtypes = [wintypes.HWND]
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    found = []
    def visit(hwnd, _):
        owner = wintypes.DWORD(); user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if (pid is None or owner.value == pid) and user.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(512); user.GetWindowTextW(hwnd, title, 512)
            if title.value == 'Setlist':
                if user.IsIconic(hwnd): user.ShowWindow(hwnd, 9)
                user.SetForegroundWindow(hwnd); found.append(hwnd); return False
        return True
    user.EnumWindows(callback_type(visit), 0)
    return bool(found)
