"""The Windows PC, through the Win32 API with ctypes. Read-only."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .platform import Foreground

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
LOCK_APPS = ("lockapp.exe", "logonui.exe")


class _LastInput(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
# 64-bit handles are cut to 32 bits without these declarations
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LastInput)]
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
_kernel32.GetTickCount.restype = wintypes.DWORD


def _process_name(hwnd) -> str:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        path = ctypes.create_unicode_buffer(size.value)
        ok = _kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size))
        return os.path.basename(path.value) if ok else ""
    finally:
        _kernel32.CloseHandle(handle)


def foreground() -> Foreground:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return Foreground("", "")
    title = ctypes.create_unicode_buffer(_user32.GetWindowTextLengthW(hwnd) + 1)
    _user32.GetWindowTextW(hwnd, title, len(title))
    return Foreground(_process_name(hwnd), title.value)


def idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input. Game controllers may not count."""
    info = _LastInput(cbSize=ctypes.sizeof(_LastInput))
    if not _user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((_kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


def is_locked(app: str) -> bool:
    return not app or app.casefold() in LOCK_APPS
