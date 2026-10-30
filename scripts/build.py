"""Build console/desktop executables and a portable zip without elevation."""
from importlib import metadata
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "TangerineXiaoAiAssistant"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
PYSTRAY_SOURCE_SHA256 = "99fb0f7ec3a551e6c96d3946ecfce0e9dc04bac7994fa64ae348921a634af70e"


def source_archives(destination, custom_library=None):
    """Ship corresponding library and application source, including rebuild scripts."""
    destination.mkdir(parents=True, exist_ok=True)
    library = destination / "pystray-0.19.5.zip"
    if custom_library is not None:
        shutil.copy2(custom_library, library)
    elif not library.exists():
        with urlopen("https://codeload.github.com/moses-palmer/pystray/zip/refs/tags/v0.19.5", timeout=60) as response:
            library.write_bytes(response.read())
    if custom_library is None and hashlib.sha256(library.read_bytes()).hexdigest() != PYSTRAY_SOURCE_SHA256:
        raise RuntimeError("pystray source checksum mismatch")
    dist = metadata.distribution("pystray")
    if dist.version != "0.19.5":
        raise RuntimeError("Review corresponding sources when changing pystray version")
    with zipfile.ZipFile(library) as upstream:
        for item in dist.files:
            if str(item).startswith("pystray/") and item.suffix == ".py":
                installed = Path(dist.locate_file(item)).read_bytes().replace(b"\r\n", b"\n")
                source = upstream.read("pystray-0.19.5/lib/" + item.as_posix()).replace(b"\r\n", b"\n")
                if installed != source:
                    raise RuntimeError("Modified pystray detected: include matching source before distribution")
    with zipfile.ZipFile(destination / f"{NAME}-{VERSION}-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        files = [ROOT / name for name in ("README.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml",
                                         "requirements-build.lock", "requirements-runtime.lock", "config.example.json")]
        for folder in ("src", "scripts", "tests", "docs", "licenses"):
            files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                         and p.suffix in (".py", ".md", ".txt") and "__pycache__" not in p.parts)
        for path in files:
            archive.write(path, path.relative_to(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pystray-source", type=Path, help="matching modified pystray source zip, for rebuilding/relinking")
    args = parser.parse_args()
    runtime_licenses = ROOT / "build" / "runtime-licenses"
    runtime_licenses.mkdir(parents=True, exist_ok=True)
    # Actual license texts from installed distributions, not hand-written summaries.
    for name in ("requests", "certifi", "charset-normalizer", "idna", "urllib3", "pyinstaller", "pycaw", "comtypes", "psutil", "pystray", "Pillow", "six"):
        dist = metadata.distribution(name)
        copied = 0
        for item in dist.files or []:
            if any(word in item.name.lower() for word in ("license", "copying", "copyright", "notice")) and item.suffix != ".py":
                source = Path(dist.locate_file(item))
                if source.is_file():
                    destination = runtime_licenses / name / str(item)
                    # Installed distribution paths must remain within this output tree.
                    if not destination.resolve().is_relative_to(runtime_licenses.resolve()):
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    copied += 1
        if not copied:
            raise RuntimeError(f"Missing license text for {name}")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python runtime license not found")
    shutil.copy2(python_license, runtime_licenses / "Python-LICENSE.txt")
    tk_license = Path(sys.base_prefix) / "tcl" / "tk8.6" / "license.terms"
    if not tk_license.is_file():
        raise RuntimeError("Tk license not found")
    shutil.copy2(tk_license, runtime_licenses / "Tk-license.terms")
    # Python's LICENSE.txt also includes Tcl/Tk notices for the embedded runtime.
    for executable, entry, mode in ((NAME, "entry.py", "--console"),
                                    (NAME + "-Desktop", "desktop_entry.py", "--windowed")):
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", mode,
            "--name", executable, "--specpath", str(ROOT / "build"),
            "--exclude-module", "setuptools", "--exclude-module", "pkg_resources",
            "--hidden-import", "pystray._win32",
            "--paths", str(ROOT / "src"),
            "--add-data", f"{ROOT / 'licenses'}:licenses",
            "--add-data", f"{runtime_licenses}:runtime-licenses",
            "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.",
            str(ROOT / "scripts" / entry),
        ], cwd=ROOT, check=True)
    portable = ROOT / "dist" / NAME
    portable.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "dist" / f"{NAME}.exe", portable / f"{NAME}.exe")
    shutil.copy2(ROOT / "dist" / f"{NAME}-Desktop.exe", portable / f"{NAME}-Desktop.exe")
    for name in ("README.md", "THIRD_PARTY_NOTICES.md", "config.example.json"):
        shutil.copy2(ROOT / name, portable / name)
    shutil.copytree(ROOT / "licenses", portable / "licenses", dirs_exist_ok=True)
    shutil.copytree(ROOT / "docs", portable / "docs", dirs_exist_ok=True)
    shutil.copytree(runtime_licenses, portable / "licenses" / "runtime", dirs_exist_ok=True)
    source_archives(portable / "source", args.pystray_source)
    for name, command in (("login", "login"), ("run", "run"), ("probe", "probe"),
                          ("configure-app", "add-app"), ("upgrade-config", "enable-local-commands")):
        content = (f'@echo off\nchcp 65001 >nul\n"%~dp0{NAME}.exe" init\n'
                   f'if errorlevel 1 goto done\n"%~dp0{NAME}.exe" {command}\n:done\npause\n')
        (portable / f"{name}.cmd").write_text(content, encoding="utf-8", newline="\r\n")
    shutil.make_archive(str(ROOT / "dist" / f"{NAME}-{VERSION}-windows-x64"), "zip", ROOT / "dist", NAME)
    package = ROOT / "dist" / f"{NAME}-{VERSION}-windows-x64.zip"
    (ROOT / "dist" / "SHA256SUMS.txt").write_text(
        f"{hashlib.sha256(package.read_bytes()).hexdigest()}  {package.name}\n", encoding="utf-8")
    print(f"Portable build: {portable}")


if __name__ == "__main__":
    main()
