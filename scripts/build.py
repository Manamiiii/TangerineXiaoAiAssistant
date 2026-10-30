"""Build a console exe and a portable folder/zip without administrator rights."""
from importlib import metadata
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
NAME = "TangerineXiaoAiAssistant"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]


def main():
    runtime_licenses = ROOT / "build" / "runtime-licenses"
    runtime_licenses.mkdir(parents=True, exist_ok=True)
    # Actual license texts from installed distributions, not hand-written summaries.
    for name in ("requests", "certifi", "charset-normalizer", "idna", "urllib3", "pyinstaller", "pycaw", "comtypes", "psutil"):
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
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--console",
        "--name", NAME, "--specpath", str(ROOT / "build"),
        "--exclude-module", "setuptools", "--exclude-module", "pkg_resources",
        "--exclude-module", "tkinter",
        "--paths", str(ROOT / "src"),
        "--add-data", f"{ROOT / 'licenses'}:licenses",
        "--add-data", f"{runtime_licenses}:runtime-licenses",
        "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.md'}:.",
        str(ROOT / "scripts" / "entry.py"),
    ], cwd=ROOT, check=True)
    portable = ROOT / "dist" / NAME
    portable.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "dist" / f"{NAME}.exe", portable / f"{NAME}.exe")
    for name in ("README.md", "THIRD_PARTY_NOTICES.md", "config.example.json"):
        shutil.copy2(ROOT / name, portable / name)
    shutil.copytree(ROOT / "licenses", portable / "licenses", dirs_exist_ok=True)
    shutil.copytree(ROOT / "docs", portable / "docs", dirs_exist_ok=True)
    shutil.copytree(runtime_licenses, portable / "licenses" / "runtime", dirs_exist_ok=True)
    for name, command in (("login", "login"), ("run", "run"), ("probe", "probe"),
                          ("configure-app", "add-app"), ("upgrade-config", "enable-local-commands")):
        content = (f'@echo off\nchcp 65001 >nul\n"%~dp0{NAME}.exe" init\n'
                   f'if errorlevel 1 goto done\n"%~dp0{NAME}.exe" {command}\n:done\npause\n')
        (portable / f"{name}.cmd").write_text(content, encoding="utf-8", newline="\r\n")
    shutil.make_archive(str(ROOT / "dist" / f"{NAME}-{VERSION}-windows-x64"), "zip", ROOT / "dist", NAME)
    print(f"Portable build: {portable}")


if __name__ == "__main__":
    main()
