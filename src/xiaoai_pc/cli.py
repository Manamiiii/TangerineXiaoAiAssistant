from __future__ import annotations

import argparse
import hashlib
from copy import deepcopy
from getpass import getpass
import json
import os
from pathlib import Path
import sys
import time

from . import __version__, config
from .bridge import Bridge
from .commands import CommandRouter
from .runtime import configure_logging, single_instance
from .secure import SecretStore, SecretStoreError
from .vendor.voxnode.account import SID_MINA, XiaomiAuthError
from .vendor.voxnode.mina import MiNA, MiNAProtocolError
from .vendor.voxnode.qrlogin import XiaomiQrLogin, CONFIRMED, EXPIRED, FAILED, SCANNED
from .xiaomi import SecureAccount, XiaomiSpeaker, require_login
from .windows_actions import get_volume, validate_app_path


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="橘子小爱电脑助手：Windows 本地命令测试版")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--data-dir", type=Path, help="覆盖本地数据目录（默认 LOCALAPPDATA）")
    root.add_argument("--config", type=Path, help="覆盖非敏感 JSON 配置路径")
    sub = root.add_subparsers(dest="command")
    sub.add_parser("init", help="生成默认配置，不覆盖现有文件")
    sub.add_parser("enable-local-commands", help="向旧配置补入音量和锁屏规则，保留设备与自定义命令")
    app = sub.add_parser("add-app", help="登记应用 EXE 白名单，不会启动应用")
    app.add_argument("name", nargs="?", help="例如：微信；省略时在本机交互输入")
    app.add_argument("path", nargs="?", help="已安装应用的绝对 EXE 路径")
    app.add_argument("--alias", action="append", default=[], help="附加名称，可重复传入")
    sub.add_parser("volume-status", help="只读取当前默认播放设备的音量与静音状态")
    login = sub.add_parser("login", help="小米扫码登录；无需在聊天中提供账号密码")
    login.add_argument("--password", action="store_true", help="改用隐藏输入的账号密码登录")
    sub.add_parser("logout", help="删除本机加密登录缓存，不影响云端设备绑定")
    devices = sub.add_parser("devices", help="列出音箱并选择设备")
    devices.add_argument("--select", action="store_true", help="交互选择；单设备自动选择")
    sub.add_parser("probe", help="检查设备列表和对话读取，只打印数量，不执行历史命令")
    sub.add_parser("tts-test", help="让已选音箱播报固定测试语句")
    run = sub.add_parser("run", help="持续监听语音；Ctrl+C 停止")
    run.add_argument("--dry-run", action="store_true", help="只验证匹配，不打开网页或播报")
    test = sub.add_parser("test-command", help="本地测试，不连接小米；默认只演练")
    test.add_argument("text", help="例如：小爱同学，让电脑打开B站")
    test.add_argument("--execute", action="store_true", help="实际执行匹配命令；锁屏命令会立即请求锁屏")
    return root


def choose_device(account, cfg: dict, config_path: Path, *, interactive=False) -> str:
    require_login(account)
    devices = [d for d in MiNA(account).device_list() if d.get("deviceID") and d.get("hardware")]
    if not devices:
        raise RuntimeError("账号下未找到音箱，请确认米家绑定账号与音箱归属。")
    for index, device in enumerate(devices, 1):
        # IDs and device names are displayed only in the local console, not persisted in logs.
        name = str(device.get("name") or device.get("alias") or "未命名音箱")
        hardware = str(device.get("hardware", ""))
        print(f"{index}. {name} ({hardware})")
    selected = cfg["xiaomi"]["device_id"]
    if not interactive:
        return selected
    if len(devices) == 1:
        index = 1
    else:
        try:
            index = int(input("输入需要使用的音箱编号："))
        except ValueError:
            raise RuntimeError("请输入列表中的数字编号。") from None
    if not 1 <= index <= len(devices):
        raise RuntimeError("音箱编号不在列表中。")
    selected = str(devices[index - 1]["deviceID"])
    cfg["xiaomi"]["device_id"] = selected
    config.save(config_path, cfg)
    print("已保存音箱选择。")
    return selected


def qr_login(account: SecureAccount, directory: Path) -> None:
    qr = XiaomiQrLogin()
    path = directory / "login-qr.png"
    try:
        qr.start()
        image = qr.fetch_qr_image()
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("登录二维码不是预期的 PNG 图片。")
        directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
        os.startfile(str(path))
        print("请用米家 App 扫描打开的二维码，并在手机上确认。不要把二维码或凭据发到聊天中。")
        deadline = time.monotonic() + min(600, max(30, qr.expires_in))
        last_state = ""
        while time.monotonic() < deadline:
            state = qr.poll()
            if state == CONFIRMED:
                account.login_with_pass_token(SID_MINA, qr.pass_token, qr.user_id, qr.device_id)
                return
            if state in (EXPIRED, FAILED):
                raise RuntimeError("二维码已失效，请重新运行 login。")
            if state == SCANNED and state != last_state:
                print("已扫描，请在手机上确认。")
            last_state = state
            time.sleep(1)
        raise RuntimeError("扫码等待超时，请重新运行 login。")
    finally:
        path.unlink(missing_ok=True)
        qr._session.close()


def perform(args, directory: Path, config_path: Path) -> int:
    if args.command == "init":
        if config_path.exists():
            config.load(config_path)
            print(f"配置已存在且有效：{config_path}")
        else:
            config.save(config_path, deepcopy(config.DEFAULT_CONFIG))
            print(f"已创建配置：{config_path}")
        return 0
    if args.command == "logout":
        SecretStore(directory / "xiaomi.dpapi").clear()
        print("本机小米登录缓存已删除。")
        return 0
    cfg = config.load(config_path)
    if args.command == "enable-local-commands":
        updated, count = config.add_local_commands(cfg)
        config.save(config_path, updated)
        print(f"已补入 {count} 条本地规则，原设备与自定义命令已保留；重启运行窗口生效。")
        return 0
    if args.command == "add-app":
        name = (args.name or input("应用名称（例如微信）：")).strip()
        path = (args.path or input("应用 EXE 的完整路径（可拖入文件）：")).strip().strip('"')
        aliases = [name, *args.alias]
        if any(not a.strip() or any(c in a for c in "{}\r\n") for a in aliases):
            raise config.ConfigError("应用名称和别名不能为空，也不能含占位符或换行。")
        try:
            validate_app_path(path)
            target = Path(path).resolve(strict=True)
            validate_app_path(str(target))
            if not target.is_file():
                raise OSError
        except ValueError as error:
            raise config.ConfigError(str(error)) from None
        except OSError:
            raise config.ConfigError("所选 EXE 文件不存在或不可访问。") from None
        cid = "app_" + hashlib.sha256(config.normalize(name).encode()).hexdigest()[:16]
        command = {"id": cid, "action": "launch_app", "phrases": [f"打开{a}" for a in aliases],
                   "path": str(target), "reply": f"已请求启动{name}"}
        cfg["commands"] = [c for c in cfg["commands"] if c["id"] != cid] + [command]
        config.save(config_path, cfg)
        print("应用已登记，未执行启动；重启运行窗口后可说：让电脑打开" + name)
        return 0
    if args.command == "volume-status":
        level, muted = get_volume()
        print(json.dumps({"volume_percent": round(level, 2), "muted": muted}, ensure_ascii=False))
        return 0
    if args.command == "test-command":
        result = CommandRouter(cfg).execute(args.text, dry_run=not args.execute)
        print(json.dumps({"ok": result.ok, "code": result.code, "reply": result.reply}, ensure_ascii=False))
        return 0 if result.ok else 2
    account = SecureAccount(SecretStore(directory / "xiaomi.dpapi"), load_existing=args.command != "login")
    try:
        if args.command == "login":
            # Explicit login must work even when the previous cached session expired.
            account.token = {}
            if args.password:
                account.username = input("小米账号（仅本次使用）：").strip()
                account.password = getpass("密码（隐藏输入，不保存）：")
                account.otp_callback = lambda method: getpass("短信/邮箱验证码（隐藏输入）：")
                account.login(SID_MINA)
            else:
                qr_login(account, directory)
            print("小米登录成功，令牌已使用当前 Windows 用户的 DPAPI 加密保存。")
            choose_device(account, cfg, config_path, interactive=True)
            return 0
        require_login(account)
        if args.command == "devices":
            choose_device(account, cfg, config_path, interactive=args.select)
            return 0
        device_id = cfg["xiaomi"]["device_id"]
        if not device_id:
            device_id = choose_device(account, cfg, config_path, interactive=True)
        speaker = XiaomiSpeaker(account, device_id)
        if args.command == "probe":
            records = speaker.latest()
            print(f"设备可访问；对话接口成功返回 {len(records)} 条记录。未打印语音内容，未执行命令。")
            return 0
        if args.command == "tts-test":
            if not speaker.say("小爱电脑助手已连接，语音播报测试"):
                raise RuntimeError("音箱拒绝播报请求。")
            print("音箱接受了播报请求；实际是否发声仍需听音确认。")
            return 0
        if args.command == "run":
            configure_logging(directory)
            return Bridge(speaker, CommandRouter(cfg), cfg, dry_run=args.dry_run).run()
        return 2
    finally:
        account.close()


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    root = parser()
    args = root.parse_args(argv)
    if args.command is None:
        root.print_help()
        return 0
    try:
        directory = (args.data_dir or config.data_directory()).resolve()
        config_path = (args.config or directory / "config.json").resolve()
        with single_instance(directory):
            return perform(args, directory, config_path)
    except KeyboardInterrupt:
        print("\n已停止。")
        return 130
    except (config.ConfigError, SecretStoreError, XiaomiAuthError, MiNAProtocolError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except RuntimeError as error:
        # Only application-authored RuntimeErrors may carry friendly local instructions.
        print(str(error), file=sys.stderr)
        return 2
    except Exception:
        print("操作失败，请检查网络、账号或设备；未记录异常原文以保护凭据。", file=sys.stderr)
        return 2
