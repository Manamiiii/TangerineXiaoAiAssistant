"""Current-user Windows DPAPI storage. No plaintext fallback."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path


class SecretStoreError(RuntimeError):
    pass


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise SecretStoreError("凭据存储需要 Windows DPAPI。")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    entropy_buffer = ctypes.create_string_buffer(b"TangerineXiaoAiAssistant-v1")
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    entropy = Blob(len(entropy_buffer) - 1, ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    # CRYPTPROTECT_UI_FORBIDDEN; omit LOCAL_MACHINE to bind to the Windows user.
    if not function(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
        raise SecretStoreError("凭据加解密失败；请在原 Windows 账号下运行，或重新登录。")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel32.LocalFree(output.data)


class SecretStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            value = json.loads(_crypt(self.path.read_bytes(), decrypt=True))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (OSError, ValueError):
            raise SecretStoreError("凭据文件损坏或不可读，请重新登录。") from None

    def save(self, value: dict) -> None:
        encrypted = _crypt(json.dumps(value).encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_bytes(encrypted)
            temporary.replace(self.path)
        except OSError:
            raise SecretStoreError("无法保存加密凭据，请检查数据目录写入权限。") from None

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
