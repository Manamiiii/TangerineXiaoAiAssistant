"""Windows shared runtime lock / exclusive installer lock, without process killing."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os


class Overlapped(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE)]


@contextmanager
def lifecycle_guard(directory, *, exclusive=False):
    if os.name != "nt":
        raise RuntimeError("此版本仅支持 Windows。")
    directory.mkdir(parents=True, exist_ok=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.LockFileEx.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
    kernel.LockFileEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(directory / "lifecycle.lock"), 0xC0000000, 3, None, 4, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise RuntimeError("无法检查安装状态，请检查本机数据目录权限。")
    try:
        overlap = Overlapped()
        if not kernel.LockFileEx(handle, 1 | (2 if exclusive else 0), 0, 1, 0, ctypes.byref(overlap)):
            raise RuntimeError("助手或安装/卸载向导正在使用程序，请正常退出后重试；不会强制结束进程。")
        yield
    finally:
        kernel.CloseHandle(handle)
