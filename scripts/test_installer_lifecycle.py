"""Exercise Setup with a baked-in fixture identity. Never operate on the real product."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import winreg

from xiaoai_pc import config
from xiaoai_pc.identity import PRODUCTION
from xiaoai_pc.lifecycle import lifecycle_guard
from xiaoai_pc.runtime import single_instance
from xiaoai_pc.secure import SecretStore
try:
    from .build_installer import build_installer, verified_payload
except ImportError:
    from build_installer import build_installer, verified_payload


def special_folder(number):
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, number, None, 0, buffer):
        raise RuntimeError("Cannot locate current-user shortcut folder")
    return Path(buffer.value)


def shortcut_target(path):
    # Load the existing Unicode shell link read-only; do not use WSH's create API.
    from comtypes.client import CreateObject
    from comtypes.persist import IPersistFile, STGM_READ
    from comtypes.shelllink import ShellLink, IShellLinkW
    shortcut = CreateObject(ShellLink, interface=IShellLinkW)
    shortcut.QueryInterface(IPersistFile).Load(str(path), STGM_READ)
    return Path(shortcut.GetPath(0))


def check_installer(package):
    package = package.resolve()
    info, identity = verified_payload(package)
    if not identity['fixture'] or identity['data_folder'] == PRODUCTION['data_folder']:
        raise RuntimeError("Refusing installer lifecycle tests on the production identity")
    local = Path(os.environ['LOCALAPPDATA']).resolve()
    data = local / identity['data_folder']
    installed = local / 'Programs' / identity['directory_name']
    key = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + identity['guid']
    desktop_link = special_folder(0x10) / (identity['display_name'] + '（安装版）.lnk')
    menu = special_folder(2) / identity['display_name']
    menu_link = menu / (identity['display_name'] + '.lnk')
    if data.exists() or installed.exists() or desktop_link.exists() or menu.exists():
        raise RuntimeError("Fixture paths already exist; preserve them and build a new fixture UUID")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            raise RuntimeError("Fixture uninstall identity already exists")
    except FileNotFoundError:
        pass
    high = package.parent / f"{identity['directory_name']}-{info['version']}-windows-x64-Setup.exe"
    low = package.parent / f"{identity['directory_name']}-0.0.1-windows-x64-Setup.exe"
    if not low.exists():
        low = build_installer(package, installer_version='0.0.1')
    checks = []
    child = None

    def passed(label):
        checks.append(label)
        print('PASS: ' + label, flush=True)

    def invoke(command, expected=0):
        result = subprocess.run(command, capture_output=True, encoding='utf-8', timeout=90,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != expected:
            raise RuntimeError(f"Fixture operation returned {result.returncode}, expected {expected}")
        return result

    def installed_version():
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as handle:
            assert winreg.QueryValueEx(handle, 'InstallLocation')[0] == str(installed)
            return winreg.QueryValueEx(handle, 'DisplayVersion')[0]

    def uninstall(expected=0):
        # NSIS's documented _?= avoids a detached child so exit status can be tested.
        # Execute an exact copy outside the install directory to allow self-file removal.
        with tempfile.TemporaryDirectory(prefix='xiaoai-uninstall-fixture-') as folder:
            copy = Path(folder) / 'Uninstall.exe'
            shutil.copy2(installed / 'Uninstall.exe', copy)
            invoke(f'"{copy}" /S _?={installed}', expected)

    def cli(*args, expected=0):
        return invoke([str(installed / 'TangerineXiaoAiAssistant.exe'), *args], expected)

    def snapshot():
        return {name: hashlib.sha256((data / name).read_bytes()).hexdigest()
                for name in ('config.json', 'config.json.bak', 'xiaomi.dpapi', 'fixture-business.json')}

    def stop_fixture():
        if child is not None and child.poll() is None:
            (data / '.fixture-stop').write_text('stop', encoding='ascii')
            child.wait(timeout=30)  # Never terminate/kill even if a test fails.

    try:
        installed.mkdir(parents=True)
        sentinel = installed / 'unrelated.txt'
        sentinel.write_text('keep', encoding='utf-8')
        invoke([str(high), '/S'], 12)
        assert sentinel.read_text('utf-8') == 'keep'
        sentinel.unlink()
        installed.rmdir()
        passed('refuses an unrecognized installation directory without deleting files')

        with tempfile.TemporaryDirectory(prefix='xiaoai-junction-fixture-') as folder:
            target = Path(folder)
            (target / 'install.ini').write_text('[Application]\nId=' + identity['guid'] + '\n', encoding='utf-8')
            (target / 'keep.txt').write_text('keep', encoding='utf-8')
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(installed), str(target)], check=True, capture_output=True)
            try:
                assert installed.is_junction()
                invoke([str(high), '/S'], 12)
                assert (target / 'keep.txt').read_text('utf-8') == 'keep'
                assert not (target / 'TangerineXiaoAiAssistant.exe').exists()
            finally:
                # Remove the junction itself only, never traverse or delete its target.
                assert installed.is_junction() and installed.resolve() == target.resolve()
                installed.rmdir()
        passed('rejects an installation junction without writing into its target')

        with lifecycle_guard(data, exclusive=True):
            invoke([str(low), '/S'], 10)
        passed('concurrent installer lock rejects installation')
        with single_instance(data):
            invoke([str(low), '/S'], 10)
        passed('legacy portable data lock rejects installation')

        invoke([str(low), '/S'])
        assert installed_version() == '0.0.1'
        assert desktop_link.is_file() and menu_link.is_file()
        expected_target = installed / 'TangerineXiaoAiAssistant-Desktop.exe'
        for link in (menu_link, desktop_link):
            # Shell links can expose an 8.3 alias; compare the actual file identity.
            target = shortcut_target(link)
            assert target.is_file() and target.samefile(expected_target), f'Shortcut target mismatch: {link.name}, target exists={target.is_file()}'
        passed('per-user install creates expected HKCU uninstall entry and shortcuts')

        cli('init')
        cfg = config.load(data / 'config.json')
        cfg['tts_reply'] = False
        cfg['commands'][0]['url'] = 'https://example.com'
        config.save(data / 'config.json', cfg)
        SecretStore(data / 'xiaomi.dpapi').save({'fixture': 'not-a-real-login'})
        (data / 'fixture-business.json').write_text('{"fixture": 1}', encoding='utf-8')
        saved = snapshot()
        assert json.loads(cli('test-command', '让电脑打开B站').stdout)['code'] == 'dry_run'
        assert json.loads(cli('test-command', '让电脑把音量调到三十').stdout)['code'] == 'dry_run'
        assert json.loads(cli('test-command', '让电脑锁屏').stdout)['code'] == 'dry_run'
        cli('test-command', '让电脑打开B站 & calc', expected=2)
        invoke([str(installed / 'TangerineXiaoAiAssistant-Desktop.exe'), 'desktop', '--smoke-test'])
        assert snapshot() == saved
        passed('installed CLI rules and real Tk/tray launch preserve fictional configuration')

        child = subprocess.Popen([str(installed / 'TangerineXiaoAiAssistant-Desktop.exe'), 'desktop', '--fixture-session'],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 40
        while not (data / '.fixture-ready').exists():
            if child.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Fixture GUI did not become ready')
            time.sleep(0.1)
        before_exe = hashlib.sha256((installed / 'TangerineXiaoAiAssistant-Desktop.exe').read_bytes()).hexdigest()
        invoke([str(high), '/S'], 10)
        uninstall(expected=10)
        assert child.poll() is None and installed_version() == '0.0.1'
        assert hashlib.sha256((installed / 'TangerineXiaoAiAssistant-Desktop.exe').read_bytes()).hexdigest() == before_exe
        assert snapshot() == saved
        passed('running real fixture GUI blocks upgrade and uninstall without process termination')
        stop_fixture()
        assert child.returncode == 0
        passed('fixture GUI exits cooperatively and releases installer lock')

        invoke([str(high), '/S'])
        assert installed_version() == info['version'] and snapshot() == saved
        passed('lower-version installer fixture upgrades while retaining config, backup and encrypted fixture data')
        invoke([str(low), '/S'], 11)
        assert installed_version() == info['version'] and snapshot() == saved
        passed('downgrade refused without changing program version or data')
        cli('init')
        with lifecycle_guard(data, exclusive=True):
            cli('init', expected=2)
        assert snapshot() == saved
        passed('frozen app refuses startup while installer holds lock; reopen retains data')

        unknown = installed / 'keep-me.txt'
        unknown.write_text('unrecognized file must survive uninstall', encoding='utf-8')
        uninstall()
        assert unknown.is_file() and snapshot() == saved
        assert not desktop_link.exists() and not menu_link.exists()
        try:
            installed_version()
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError('Uninstall registration remains')
        assert {p.name for p in installed.iterdir()} == {'keep-me.txt'}
        passed('uninstall removes owned files/shortcuts/registration but retains all data and unknown files')
        unknown.unlink()
        installed.rmdir()
        invoke([str(high), '/S'])
        cli('init')
        assert snapshot() == saved
        assert SecretStore(data / 'xiaomi.dpapi').load() == {'fixture': 'not-a-real-login'}
        invoke([str(installed / 'TangerineXiaoAiAssistant-Desktop.exe'), 'desktop', '--smoke-test'])
        passed('reinstall and real window reopen recover retained config and encrypted fixture data')
        uninstall()
        assert not installed.exists() and not desktop_link.exists() and not menu.exists()
        # Only the UUID-specific fixture data created by this test may be removed.
        # Packaged desktop hosts can virtualize a new child beneath LOCALAPPDATA.
        # Still require the resolved target to stay inside that root and own UUID.
        assert data.resolve().is_relative_to(local) and data.resolve().name == identity['data_folder'] and identity['fixture']
        assert not data.is_symlink() and not data.is_junction()
        shutil.rmtree(data)
        passed('test-only installation and profile cleanup complete')
        (package.parent / 'lifecycle-results.json').write_text(json.dumps(
            {'version': info['version'], 'fixture': True, 'checks': checks,
             'upgrade_scope': 'lower installer version using current code; not historical business migration',
             'production_identity_tested': False, 'clean_windows_tested': False}, ensure_ascii=False, indent=2), encoding='utf-8')
        return checks
    finally:
        stop_fixture()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, required=True)
    args = parser.parse_args()
    checks = check_installer(args.package_dir)
    print(f'Installer lifecycle: PASS ({len(checks)} checks; isolated fixture only)')
