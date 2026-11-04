"""Build a per-user Windows x64 Setup from a verified portable payload. No publishing."""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import tempfile
from urllib.request import urlopen
import zipfile

from xiaoai_pc.identity import validate

ROOT = Path(__file__).resolve().parents[1]
NAME = "TangerineXiaoAiAssistant"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quote(value):
    value = str(value)
    if '\n' in value or '\r' in value:
        raise ValueError("Newlines are not allowed in installer definitions")
    return '"' + value.replace('$', '$$').replace('"', '$\\"') + '"'


@contextmanager
def nsis_tool():
    lock = json.loads((ROOT / "installer/windows/toolchain.json").read_text("utf-8"))
    cache = ROOT / "build/tools"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / ("nsis-" + lock["version"] + ".zip")
    if not archive.exists():
        with urlopen(lock["url"], timeout=60) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000 or hashlib.sha256(data).hexdigest() != lock["sha256"]:
            raise RuntimeError("NSIS download checksum mismatch")
        archive.write_bytes(data)
    if sha256(archive) != lock["sha256"]:
        raise RuntimeError("NSIS cache checksum mismatch; compiler not executed")
    with tempfile.TemporaryDirectory(prefix="nsis-", dir=cache) as folder:
        directory = Path(folder).resolve()
        with zipfile.ZipFile(archive) as package:
            for name in package.namelist():
                if not (directory / name).resolve().is_relative_to(directory):
                    raise RuntimeError("Invalid compiler archive path")
            package.extractall(directory)
        tool = directory / ("nsis-" + lock["version"]) / "makensis.exe"
        if sha256(tool.parent / "COPYING") != sha256(ROOT / "licenses/NSIS-COPYING.txt"):
            raise RuntimeError("NSIS license changed; review before distributing")
        yield tool


def verified_payload(portable):
    portable = portable.resolve()
    info = json.loads((portable / "build-info.json").read_text("utf-8"))
    identity = validate(info["identity"])
    expected = info["files"]
    actual = {p.relative_to(portable).as_posix() for p in portable.rglob('*') if p.is_file()}
    if actual != set(expected) | {"build-info.json"}:
        raise RuntimeError("Portable file list changed; rebuild before creating Setup")
    for name, digest in expected.items():
        path = portable / name
        if not path.resolve().is_relative_to(portable) or path.is_symlink() or sha256(path) != digest:
            raise RuntimeError("Portable file changed; rebuild before creating Setup")
    if info["platform"] != "windows-x64":
        raise RuntimeError("This installer supports Windows x64 only")
    return info, identity


def build_installer(portable, *, installer_version=None):
    if platform.system() != "Windows" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Build Windows x64 Setup on Windows x64")
    portable = portable.resolve()
    info, identity = verified_payload(portable)
    version = installer_version or info["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Installer version must have three numeric parts")
    if version != info["version"] and not identity["fixture"]:
        raise ValueError("Only isolated fixture installers may override the version")
    prefix = identity["directory_name"]
    output = portable.parent / f"{prefix}-{version}-windows-x64-Setup.exe"
    if output.exists():
        raise RuntimeError("Setup already exists; choose a fresh output directory")
    with nsis_tool() as compiler, tempfile.TemporaryDirectory(prefix="installer-", dir=ROOT / "build") as folder:
        stage = Path(folder)
        files = sorted(p for p in portable.rglob('*') if p.is_file())
        install, uninstall, directories = [], [], set()
        for path in files:
            relative = path.relative_to(portable)
            parent = relative.parent
            install += ['SetOutPath ' + quote("$INSTDIR" + ("\\" + str(parent) if str(parent) != '.' else '')).replace('$$INSTDIR', '$INSTDIR'),
                        'File ' + quote(path)]
            target = quote("$INSTDIR\\" + str(relative)).replace('$$INSTDIR', '$INSTDIR')
            uninstall += ['IfFileExists ' + target + ' 0 +4', 'ClearErrors', 'Delete ' + target,
                          'IfErrors uninstall_failed']
            directories.update(p for p in relative.parents if str(p) != '.')
        uninstall += ['RMDir ' + quote("$INSTDIR\\" + str(p)).replace('$$INSTDIR', '$INSTDIR')
                      for p in sorted(directories, key=lambda p: len(p.parts), reverse=True)]
        checks = []
        targets = {"$INSTDIR", "$INSTDIR\\install.ini", "$INSTDIR\\Uninstall.exe"}
        targets.update("$INSTDIR\\" + str(p.relative_to(portable)) for p in files)
        targets.update("$INSTDIR\\" + str(p) for p in directories)
        for target in sorted(targets):
            escaped = quote(target).replace('$$INSTDIR', '$INSTDIR')
            checks += ["System::Call 'kernel32::GetFileAttributesW(w " + escaped + ") i.r0'",
                       '${If} $0 != -1', 'IntOp $1 $0 & 0x400', '${If} $1 != 0',
                       'Goto paths_unsafe', '${EndIf}', '${EndIf}']
        (stage / "check-paths.nsh").write_text('\n'.join(checks) + '\n', encoding="utf-8-sig")
        (stage / "install-files.nsh").write_text('\n'.join(install) + '\n', encoding="utf-8-sig")
        (stage / "uninstall-files.nsh").write_text('\n'.join(uninstall) + '\n', encoding="utf-8-sig")
        definitions = {"DISPLAY_NAME": identity["display_name"], "APP_GUID": identity["guid"],
                       "DIRECTORY_NAME": identity["directory_name"], "DATA_FOLDER": identity["data_folder"],
                       "STARTUP_VALUE": identity["startup_value"], "INSTALL_VERSION": version,
                       "OUTPUT_FILE": output, "APP_ICON": portable / "app.ico", "LICENSE_FILE": portable / "LICENSE",
                       "INSTALL_FILES": stage / "install-files.nsh", "UNINSTALL_FILES": stage / "uninstall-files.nsh",
                       "CHECK_PATHS": stage / "check-paths.nsh",
                       "SIZE_KB": sum(p.stat().st_size for p in files) // 1024 + 1024}
        if identity["fixture"] and installer_version == "0.0.1":
            definitions["LEGACY_LAYOUT_FIXTURE"] = 1
        includes = stage / "definitions.nsh"
        includes.write_text('\n'.join('!define ' + name + ' ' + quote(value) for name, value in definitions.items()) + '\n', encoding="utf-8-sig")
        subprocess.run([str(compiler), "/NOCONFIG", "/INPUTCHARSET", "UTF8", "/V2",
                        "/DDEFINITIONS=" + str(includes), str(ROOT / "installer/windows/setup.nsi")], check=True)
    checksums = portable.parent / "SHA256SUMS.txt"
    with checksums.open('a', encoding="utf-8", newline='\n') as stream:
        stream.write(sha256(output) + "  " + output.name + "\n")
    print("Setup built locally: " + output.name)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, required=True)
    parser.add_argument('--installer-version', help='fixture-only lower version for upgrade tests')
    args = parser.parse_args()
    build_installer(args.package_dir, installer_version=args.installer_version)
