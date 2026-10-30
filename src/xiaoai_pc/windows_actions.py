"""Narrow Windows APIs. Never accept voice text as a program or shell command."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess


class LocalActionError(RuntimeError):
    """Application-authored, credential-free messages safe for local display."""


SHELL_HOSTS = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "wscript.exe", "cscript.exe", "mshta.exe",
    "rundll32.exe", "regsvr32.exe", "python.exe", "pythonw.exe", "py.exe", "node.exe",
    "bash.exe", "sh.exe", "wsl.exe", "conhost.exe", "wt.exe", "windowsterminal.exe",
}


def validate_app_path(value: str) -> None:
    if not isinstance(value, str) or not value or any(ord(c) < 32 or c in '<>"|?*' for c in value):
        raise ValueError("应用路径必须是本机绝对 EXE 路径。")
    path = PureWindowsPath(value)
    if (not path.is_absolute() or not re.fullmatch(r"[a-zA-Z]:", path.drive)
            or path.suffix.casefold() != ".exe" or ".." in path.parts
            or ":" in value[2:] or path.name.casefold() in SHELL_HOSTS):
        raise ValueError("仅允许本机绝对 EXE 路径，不允许脚本、网络路径或命令解释器。")


def launch_app(path: str) -> None:
    validate_app_path(path)
    if os.name != "nt":
        raise LocalActionError("启动应用需要 Windows。")
    try:
        target = Path(path).resolve(strict=True)
        validate_app_path(str(target))
        if not target.is_file():
            raise OSError
        subprocess.Popen([str(target)], cwd=str(target.parent), shell=False, close_fds=True)
    except (OSError, ValueError):
        raise LocalActionError("应用无法启动，请检查登记的 EXE 路径或重新登记。") from None


def _request_lock() -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.LockWorkStation.argtypes = []
    user32.LockWorkStation.restype = wintypes.BOOL
    return bool(user32.LockWorkStation())


def lock_workstation() -> None:
    if os.name != "nt" or not _request_lock():
        raise LocalActionError("Windows 未接受锁屏请求，请确认在已登录的桌面会话中运行。")


def _with_volume(callback):
    if os.name != "nt":
        raise LocalActionError("音量控制需要 Windows。")
    import comtypes
    from pycaw.pycaw import AudioUtilities

    # Balance explicit COM initialization on the thread executing the command.
    comtypes.CoInitialize()
    device = endpoint = None
    try:
        device = AudioUtilities.GetSpeakers()
        if device is None:
            raise LocalActionError("没有可用的默认播放设备。")
        endpoint = device.EndpointVolume
        return callback(endpoint)
    finally:
        # COM objects must be released while this thread's apartment is alive.
        endpoint = device = None
        comtypes.CoUninitialize()


def get_volume() -> tuple[float, bool]:
    try:
        return _with_volume(lambda endpoint: (
            float(endpoint.GetMasterVolumeLevelScalar() * 100), bool(endpoint.GetMute())
        ))
    except Exception:
        raise LocalActionError("无法读取系统音量，请检查默认播放设备。") from None


def set_volume(level: int) -> tuple[int, bool]:
    if type(level) is not int or not 0 <= level <= 100:
        raise LocalActionError("音量必须是 0 到 100 的整数。")
    def apply(endpoint):
        endpoint.SetMasterVolumeLevelScalar(level / 100.0, None)
        actual = float(endpoint.GetMasterVolumeLevelScalar() * 100)
        muted = bool(endpoint.GetMute())
        if abs(actual - level) > 1:
            raise LocalActionError("音量读回值与目标不符，请检查默认播放设备。")
        return round(actual), muted
    try:
        return _with_volume(apply)
    except LocalActionError:
        raise
    except Exception:
        raise LocalActionError("系统音量设置失败，请检查默认播放设备。") from None
