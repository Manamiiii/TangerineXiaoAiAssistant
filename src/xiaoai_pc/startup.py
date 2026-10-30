"""Opt-in, current-user startup registration. No elevation or startup-time writes."""
from pathlib import Path
import subprocess
import sys
import winreg
from .config import data_directory

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TangerineXiaoAiAssistant"


def command_line(directory: Path, config_path: Path) -> str:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).with_name("TangerineXiaoAiAssistant-Desktop.exe")
        args = [str(executable)]
    else:
        executable = Path(sys.executable).with_name("pythonw.exe")
        args = [str(executable), "-m", "xiaoai_pc"]
    if not executable.is_file():
        raise RuntimeError("找不到桌面启动程序，请完整解压便携包后再启用自启。")
    if directory.resolve() != data_directory().resolve():
        args += ["--data-dir", str(directory.resolve())]
    if config_path.resolve() != (directory / "config.json").resolve():
        args += ["--config", str(config_path.resolve())]
    args += ["desktop", "--hidden"]
    result = subprocess.list2cmdline(args)
    if len(result) > 260:
        raise RuntimeError("程序或数据目录路径太长，请移至较短的固定目录再启用自启。")
    return result


def read() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, kind = winreg.QueryValueEx(key, VALUE_NAME)
            return value if kind == winreg.REG_SZ else None
    except FileNotFoundError:
        return None


def set_enabled(enabled: bool, directory: Path, config_path: Path) -> None:
    desired = command_line(directory, config_path) if enabled else None
    if read() == desired:
        return
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if desired is not None:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, desired)
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
